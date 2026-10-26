"""Context-preserving regional inference for the standalone Hecate runtime.

The region uses the full input's tile grid, edge tile, batch groups and weights.
Only intersecting batch groups are evaluated; accumulators cover only the ROI.
Coordinates are half-open X0 Y0 X1 Y1 in the input's voxel grid.

The global-grid principle has prior art: ScrollPrize/villa PR #1247.
Model, normalization and blending are derived from MIT-licensed scrollprize/hecate
revision 9cb86e500e944b11a06a7020403cde5dffb5bcb2. No model weights change.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import numpy as np

RUNTIME_SHA256 = 'c232c18a1a86cfb91257a00db13288202bb8ae33732ba26f7291a9b8adb8da59'


def axis_starts(length, patch, stride):
    if length < 1 or patch < 1 or not 0 < stride <= patch:
        raise ValueError('Positive dimensions and stride <= patch required')
    return list(range(0,max(0,length-patch),stride))+[max(0,length-patch)]


def schedule(shape, patch_size, roi, stride=None, batch_size=1):
    """Plan only: no image data, weights or Torch needed."""
    depth,h,w=map(int,shape); d,p,px=map(int,patch_size)
    if len(roi)!=4 or any(isinstance(v,bool) or int(v)!=v for v in roi):
        raise ValueError('Integer half-open XY bounds required')
    x0,y0,x1,y1=map(int,roi)
    stride=p//2 if stride is None else stride
    if not 0<=x0<x1<=w or not 0<=y0<y1<=h or depth<d or px!=p or batch_size<1:
        raise ValueError('Invalid ROI, depth, patch or batch size')
    origins=[(y,x) for y in axis_starts(h,p,stride) for x in axis_starts(w,p,stride)]
    intersects=lambda y,x: y<y1 and y+p>y0 and x<x1 and x+p>x0
    groups=[]
    for start in range(0,len(origins),batch_size):
        group=origins[start:start+batch_size]
        if any(intersects(y,x) for y,x in group):
            groups.append({'global_start':start,'origins':group})
    required=[o for g in groups for o in g['origins']]
    return {'shape_zyx':[depth,h,w], 'patch_size':[d,p,p], 'roi_xyxy':[x0,y0,x1,y1],
        'stride':stride, 'batch_size':batch_size, 'groups':groups,
        'full_tiles':len(origins), 'scheduled_tiles':len(required),
        'contributing_tiles':sum(intersects(y,x) for y,x in required),
        'read_context_xyxy':[min(x for y,x in required),min(y for y,x in required),
            min(w,max(x+p for y,x in required)),min(h,max(y+p for y,x in required))],
        'temporary_2d_bytes':8*(y1-y0)*(x1-x0),
        'temporary_3d_bytes':4*(d+1)*(y1-y0)*(x1-x0),
        'scope':'Counts include blank tiles. Preserve complete original batch groups; actual neural tile count can be lower for empty CT.'}


def predict_roi(model,volume,output,roi,reverse=False,stride=None,batch_size=1,precision='fp32',three_d=False):
    """Same uint8 contract as upstream, but output covers only ROI in XY.

    A lazy Zarr-like source is accepted. This function never converts the full
    source to an ndarray. Deterministic equivalence requires the same runtime,
    model, device, precision, stride and batch size as the full run.
    """
    import torch
    if len(volume.shape)!=3 or np.dtype(volume.dtype)!=np.dtype('uint8'):
        raise ValueError('Input must be uint8 ZYX')
    plan=schedule(volume.shape,model.patch_size,roi,stride,batch_size)
    depth,h,w=plan['shape_zyx']; d,p,_=model.patch_size
    x0,y0,x1,y1=plan['roi_xyxy']; rh,rw=y1-y0,x1-x0
    expected=(depth,rh,rw) if three_d else (rh,rw)
    if tuple(output.shape)!=expected or output.dtype!=np.uint8:
        raise ValueError(f'Output must be uint8 with shape {expected}')
    device=next(model.parameters()).device
    if precision not in ('fp32','bf16') or (precision=='bf16' and device.type!='cuda'):
        raise ValueError('bf16 requires CUDA; otherwise use fp32')
    if model.training:
        raise ValueError('Inference requires model.eval()')
    output[:]=0
    z0=depth//2-d//2
    zs=slice(depth-z0-d,depth-z0) if reverse else slice(z0,z0+d)
    win=torch.hann_window(p,periodic=False);win=win[:,None]*win[None,:]
    win=(win/win.max().clamp_min(torch.finfo(torch.float32).eps)).clamp_min(.001)
    window=win.numpy(); win=win.to(device)
    began=time.perf_counter(); neural_tiles=0; neural_batches=0; read_voxels=0
    with tempfile.TemporaryDirectory(prefix='hecate-roi-') as tmp,torch.inference_mode():
        numerator=np.memmap(Path(tmp)/'sum',mode='w+',dtype='float32',shape=(d,rh,rw) if three_d else (rh,rw))
        denominator=np.memmap(Path(tmp)/'weight',mode='w+',dtype='float32',shape=(rh,rw))
        numerator[:]=0;denominator[:]=0
        for group in plan['groups']:
            active=[]; patches=[]
            for y,x in group['origins']:
                ph,pw=min(p,h-y),min(p,w-x)
                ay,ax,by,bx=max(y,y0),max(x,x0),min(y+ph,y1),min(x+pw,x1)
                if ay<by and ax<bx:
                    denominator[ay-y0:by-y0,ax-x0:bx-x0]+=window[ay-y:by-y,ax-x:bx-x]
                raw=np.asarray(volume[zs,y:y+ph,x:x+pw]);read_voxels+=int(raw.size)
                if reverse:raw=raw[::-1]
                if not raw.any():continue
                patch=np.zeros((d,p,p),dtype=np.uint8);patch[:,:ph,:pw]=raw
                patches.append(patch);active.append((y,x,ay,ax,by,bx))
            if not patches:continue
            neural_tiles+=len(patches);neural_batches+=1
            raw=torch.from_numpy(np.stack(patches)).to(device)
            support=raw.any(1)
            normalized=np.stack(patches).astype(np.float32);normalized/=model.divisor
            image=torch.from_numpy(normalized[:,None]).to(device)
            valid=support[:,None,None].expand(-1,1,d,-1,-1)
            with torch.autocast(device_type=device.type,dtype=torch.bfloat16,enabled=precision=='bf16'):
                logits=model.forward_3d(image) if three_d else model(image,valid)
                probability=logits.float().sigmoid()[:,0]
            if three_d:support=support[:,None]
            weighted=(probability*support*win).cpu().numpy()
            for pred,(y,x,ay,ax,by,bx) in zip(weighted,active):
                if ay<by and ax<bx:
                    numerator[...,ay-y0:by-y0,ax-x0:bx-x0]+=pred[...,ay-y:by-y,ax-x:bx-x]
            del raw,support,normalized,image,valid,logits,probability,weighted,patches
        if np.any(denominator<=0):raise RuntimeError('ROI has an uncovered output pixel')
        if three_d and model.margin:
            numerator[:model.margin]=0;numerator[-model.margin:]=0
        for y in range(0,rh,128):
            for x in range(0,rw,256):
                prob=numerator[...,y:y+128,x:x+256]/denominator[y:y+128,x:x+256]
                if not np.isfinite(prob).all():raise FloatingPointError('Nonfinite inference output')
                values=np.rint(prob.clip(0,1)*255).astype(np.uint8)
                if three_d:output[zs,y:y+128,x:x+256]=values[::-1] if reverse else values
                else:output[y:y+128,x:x+256]=values
        del numerator,denominator
    return {**plan,'neural_tiles':neural_tiles,'neural_batches':neural_batches,
        'source_voxels_read_including_overlap':read_voxels,'elapsed_seconds':time.perf_counter()-began,
        'output_dimensions':'ZYX' if three_d else 'YX','reverse_z':bool(reverse),
        'evaluated_z_interval':[zs.start+model.margin,zs.stop-model.margin],
        'output_origin_in_source_xyz':[x0,y0,0],
        'outside_evaluated_z':'zero; not evaluated',
        'probabilities':'uint8 = round(255 * probability); no min-max scaling'}


def load_runtime(path):
    path=Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=RUNTIME_SHA256:
        raise ValueError('Runtime differs from the tested pinned Hecate revision')
    spec=importlib.util.spec_from_file_location('hecate_roi_upstream',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',required=True,type=Path)
    parser.add_argument('--checkpoint',type=Path)
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--array',default='0')
    parser.add_argument('--spacing-um',required=True,type=float,choices=(2.4,9.6))
    parser.add_argument('--roi',required=True,type=int,nargs=4,metavar=('X0','Y0','X1','Y1'))
    parser.add_argument('--output',type=Path,help='2D PNG or NPY')
    parser.add_argument('--output-3d',type=Path,help='3D uint8 NPY, aligned to source Z indices')
    parser.add_argument('--device',default='cpu');parser.add_argument('--threads',type=int,default=4)
    parser.add_argument('--stride',type=int);parser.add_argument('--batch-size',type=int,default=1)
    parser.add_argument('--precision',choices=('fp32','bf16'),default='fp32')
    parser.add_argument('--reverse',action='store_true');parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    import torch
    torch.set_num_threads(args.threads)
    runtime=load_runtime(args.runtime);volume=runtime.open_volume(args.input,args.array)
    patch=(64,256,256) if args.spacing_um==2.4 else (16,64,64)
    if args.dry_run:
        print(json.dumps(schedule(volume.shape,patch,args.roi,args.stride,args.batch_size),indent=2));return
    if not args.checkpoint or not (args.output or args.output_3d):parser.error('Checkpoint and an output are required')
    for output,allowed in ((args.output,('.png','.npy')),(args.output_3d,('.npy',))):
        if output and (output.suffix.lower() not in allowed or output.exists() or output.with_suffix(output.suffix+'.json').exists()):
            parser.error('Choose new output paths with supported suffixes; no overwrite')
    model=runtime.load_model(args.checkpoint,args.device)
    if model.sampling_um!=args.spacing_um:parser.error('Input spacing does not match checkpoint')
    x0,y0,x1,y1=args.roi
    for output,three_d in ((args.output,False),(args.output_3d,True)):
        if output is None:continue
        output.parent.mkdir(parents=True,exist_ok=True)
        shape=(volume.shape[0],y1-y0,x1-x0) if three_d else (y1-y0,x1-x0)
        partial=output.with_name(output.name+'.partial')
        if partial.exists():parser.error(f'Incomplete output exists: {partial}')
        with tempfile.TemporaryDirectory(prefix='hecate-roi-output-') as tmp:
            array=np.lib.format.open_memmap(Path(tmp)/'output.npy',mode='w+',dtype='uint8',shape=shape)
            metadata=predict_roi(model,volume,array,args.roi,args.reverse,args.stride,args.batch_size,args.precision,three_d)
            array.flush()
            if output.suffix.lower()=='.png':runtime.write_png(array,partial)
            else:
                import shutil
                shutil.copyfile(Path(tmp)/'output.npy',partial)
            del array
            partial.replace(output)
        metadata.update({'runtime_sha256':RUNTIME_SHA256,'checkpoint':args.checkpoint.name,
            'sampling_um':args.spacing_um,'precision':args.precision,
            'source':str(args.input),'source_array':args.array,
            'coordinate_note':'ROI indices refer to the supplied full surface array; source world transforms are not inferred.'})
        output.with_suffix(output.suffix+'.json').write_text(json.dumps(metadata,indent=2)+'\n')
        print(output)


if __name__=='__main__':main()
