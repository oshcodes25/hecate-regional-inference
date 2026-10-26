"""Portable saved-result verification and optional model rerun for the package."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--rerun',action='store_true',help='Run models; requires local checkpoints and Torch')
    parser.add_argument('--case',type=int,default=0)
    parser.add_argument('--models',type=Path,help='Directory containing hecate_2.4um.pth and/or hecate_9.6um.pth')
    parser.add_argument('--output',type=Path,help='New output directory for a model rerun')
    args=parser.parse_args();package=args.package.resolve()
    import numpy as np
    manifest=json.loads((package/'MANIFEST.json').read_text())
    for record in manifest['files']:
        p=package/record['path']
        if p.stat().st_size!=record['bytes'] or digest(p)!=record['sha256']:raise ValueError(f'Changed file: {p}')
    cases=json.loads((package/'cases.json').read_text());checked=0
    for case in cases:
        x0,y0,x1,y1=case['roi_xyxy']
        full=np.load(package/case['outputs']['full'],mmap_mode='r',allow_pickle=False)[...,y0:y1,x0:x1]
        candidate=np.load(package/case['outputs']['roi'],mmap_mode='r',allow_pickle=False)
        if not np.array_equal(full,candidate):raise AssertionError(f"Saved ROI mismatch in case {case['index']}")
        naive=np.load(package/case['outputs']['naive'],mmap_mode='r',allow_pickle=False)
        mismatch=int(np.count_nonzero(naive!=full))
        if mismatch!=case['naive_differing_values']:raise AssertionError('Naive difference count changed')
        checked+=int(full.size)
    print(f'PASS: {len(manifest["files"])} file hashes; {len(cases)} cases; {checked:,} regional values exactly equal.')
    if not args.rerun:return
    if not args.models or not args.output:parser.error('--rerun requires --models and a new --output directory')
    if not 0<=args.case<len(cases):parser.error('Unknown case')
    args.output.mkdir(parents=True,exist_ok=False)
    import torch
    sys.path.insert(0,str(package/'src'))
    from hecate_roi import load_runtime,predict_roi
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    torch.manual_seed(20261026);torch.use_deterministic_algorithms(True)
    case=cases[args.case];checkpoint=args.models/case['checkpoint_name']
    if digest(checkpoint)!=case['checkpoint_sha256']:raise ValueError('Checkpoint hash differs')
    runtime=load_runtime(package/'data/paired-resolution-audit/hecate-runtime-pinned.py')
    volume=np.load(package/case['input'],allow_pickle=False)
    if case['sampling_um']==9.6:
        z,h,w=volume.shape
        volume=np.rint(volume.reshape(z//4,4,h//4,4,w//4,4).mean(axis=(1,3,5))).astype(np.uint8)
    model=runtime.load_model(checkpoint,'cpu');d,p,_=model.patch_size
    with torch.inference_mode():
        image=torch.from_numpy(volume[:d,:p,:p].astype(np.float32)[None,None]/np.float32(model.divisor))
        model.forward_3d(image) if case['three_d'] else model(image)
    del image
    outputs={};timings={};x0,y0,x1,y1=case['roi_xyxy']
    for name in case['order']:
        source=volume[:,y0:y1,x0:x1] if name=='naive' else volume
        yx=(y1-y0,x1-x0) if name=='roi' else source.shape[-2:]
        output=np.zeros(((volume.shape[0],) if case['three_d'] else ())+yx,np.uint8)
        start=time.perf_counter()
        with torch.inference_mode():
            if name=='roi':predict_roi(model,volume,output,case['roi_xyxy'],case['reverse'],batch_size=case['batch_size'],three_d=case['three_d'])
            else:runtime.predict(model,source,output,case['reverse'],batch_size=case['batch_size'],three_d=case['three_d'])
        timings[name]=time.perf_counter()-start
        np.save(args.output/(name+'.npy'),output,allow_pickle=False);outputs[name]=output
    ref=outputs['full'][...,y0:y1,x0:x1]
    result={'case':args.case,'roi_differing_values':int(np.count_nonzero(ref!=outputs['roi'])),
        'naive_differing_values':int(np.count_nonzero(ref!=outputs['naive'])),'seconds':timings,
        'scope':'A fresh local timing; hardware/backend differences may affect speed and outputs relative to the supplied original run.'}
    (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if result['roi_differing_values']:raise AssertionError('Local full/ROI equivalence failed')


if __name__=='__main__':main()
