"""Repeatable full-field / regional / carefully cropped-context comparison.

Standalone: Python, NumPy and Torch only. No workspace imports. This does not
score ink accuracy. A halo baseline is an important existing alternative.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time
import numpy as np


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def context_box(runtime,shape,patch,stride,box):
    """Independent baseline: find complete original tiles touching the ROI."""
    x0,y0,x1,y1=box;h,w=shape[-2:]
    ys=[y for y in runtime.axis_starts(h,patch,stride) if y<y1 and y+patch>y0]
    xs=[x for x in runtime.axis_starts(w,patch,stride) if x<x1 and x+patch>x0]
    if not ys or not xs:raise ValueError('No contributing context')
    return (min(xs),min(ys),min(w,max(xs)+patch),min(h,max(ys)+patch))


def regions(shape,sampling):
    h,w=shape[-2:]
    if sampling==2.4:return {'centre':(144,144,208,208)}
    if sampling==9.6:return {'edge':(0,0,16,16),'centre':(36,36,52,52),'large':(16,16,w-16,h-16)}
    raise ValueError('Unsupported spacing')


def operations(names,repeat):
    r=[('regional',n) for n in names];h=[('halo',n) for n in names];f=[('full',None)]
    return (f+r+h,r+h+f,h+f+r)[repeat%3]


def run(args):
    import torch
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(4);torch.set_num_interop_threads(1);torch.manual_seed(20261026)
    torch.use_deterministic_algorithms(True)
    reader=load_module('registered_roi_reader',args.reader)
    runtime=reader.load_runtime(args.runtime)
    volume=np.load(args.input,allow_pickle=False)
    if args.sampling==9.6:
        z,h,w=volume.shape
        if z%4 or h%4 or w%4:raise ValueError('Exact block averaging requires divisible dimensions')
        volume=np.rint(volume.reshape(z//4,4,h//4,4,w//4,4).mean(axis=(1,3,5))).astype(np.uint8)
    requested=regions(volume.shape,args.sampling)
    model=runtime.load_model(args.checkpoint,'cpu')
    if model.sampling_um!=args.sampling:raise ValueError('Checkpoint/input spacing differs')
    d,p,_=model.patch_size;stride=p//2
    calls={'tiles':0,'batches':0};original=model.features_logits
    def count(image):
        calls['tiles']+=len(image);calls['batches']+=1;return original(image)
    model.features_logits=count
    with torch.inference_mode():
        model(torch.from_numpy(volume[:d,:p,:p].astype(np.float32)[None,None]/np.float32(model.divisor)))
    records=[];began=time.monotonic()
    for repeat in range(3):
        outputs={};trial=[]
        for method,name in operations(list(requested),repeat):
            calls.update(tiles=0,batches=0);box=requested.get(name);context=None
            if method=='full':source=volume;shape=volume.shape[-2:]
            elif method=='regional':source=volume;shape=(box[3]-box[1],box[2]-box[0])
            else:
                context=context_box(runtime,volume.shape,p,stride,box)
                ax,ay,bx,by=context;source=volume[:,ay:by,ax:bx];shape=source.shape[-2:]
            array=np.zeros(shape,np.uint8);started=time.perf_counter()
            with torch.inference_mode():
                if method=='regional':reader.predict_roi(model,source,array,box,reverse=args.reverse,batch_size=1)
                else:runtime.predict(model,source,array,reverse=args.reverse,batch_size=1)
            elapsed=time.perf_counter()-started
            if method=='halo':
                x0,y0,x1,y1=box;array=array[y0-context[1]:y1-context[1],x0-context[0]:x1-context[0]].copy()
            label=f'{repeat}-{method}'+('-'+name if name else '')
            path=out/(label+'.npy');np.save(path,array,allow_pickle=False)
            outputs[method,name]=array
            trial.append({'repeat':repeat,'method':method,'region':name,'roi_xyxy':box,'context_xyxy':context,
                'seconds':elapsed,'neural_tiles':calls['tiles'],'neural_batches':calls['batches'],
                'temporary_accumulator_bytes':int(8*shape[0]*shape[1]),
                'output':path.name,'output_sha256':sha(path)})
            rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if time.monotonic()-began>args.seconds or rss>8*1024**3:raise RuntimeError('Registered worker resource cap exceeded')
        for row in trial:
            if row['method']=='full':continue
            x0,y0,x1,y1=row['roi_xyxy'];reference=outputs['full',None][y0:y1,x0:x1]
            value=outputs[row['method'],row['region']]
            row['different_values']=int(np.count_nonzero(value!=reference))
        if repeat and not np.array_equal(outputs['full',None],np.load(out/'0-full.npy',allow_pickle=False)):
            raise ValueError('Full-field output changed between repeats')
        records.extend(trial)
        (out/'checkpoint.json').write_text(json.dumps({'completed_repeats':repeat+1,'rows':records},indent=2)+'\n')
    result={'status':'completed','sample':args.sample,'sampling_um':args.sampling,'reverse':args.reverse,
        'recorded_at':datetime.now(timezone.utc).isoformat(),'input_shape':list(volume.shape),'rows':records,
        'input_sha256':sha(args.input),'checkpoint_sha256':sha(args.checkpoint),'reader_sha256':sha(args.reader),
        'runtime_sha256':sha(args.runtime),'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024),
        'wall_seconds_excluding_load_warmup':time.monotonic()-began,
        'scope':'CPU float32, batch1, three balanced-order repeats. Existing CT fields; no ink labels or accuracy claim. Speed relative to full inference and correctly selected surrounding-context cropping is reported separately.'}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('Completed',args.sample,args.sampling)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('reader','runtime','checkpoint','input','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--sample',required=True);p.add_argument('--sampling',required=True,type=float,choices=(2.4,9.6))
    p.add_argument('--reverse',action='store_true');p.add_argument('--seconds',type=float,default=600)
    run(p.parse_args())
