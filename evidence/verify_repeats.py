"""Independently verify the saved three-repeat Hecate comparison, without ML packages.

This checks saved predictions and recorded arithmetic. It does not execute the
model, independently measure time, or establish physical ink accuracy.
"""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent
helper=HERE/'verify.py'
if not helper.exists():helper=HERE/'verify_hecate_roi_standard.py'
spec=importlib.util.spec_from_file_location('saved_array_verifier',helper)
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)


def axis(length,patch):
    last=max(0,length-patch);points=list(range(0,last+1,patch//2))
    if points[-1]!=last:points.append(last)
    return points


def context(shape,patch,box):
    h,w=shape;x0,y0,x1,y1=box
    xs=[x for x in axis(w,patch) if x<x1 and x+patch>x0]
    ys=[y for y in axis(h,patch) if y<y1 and y+patch>y0]
    return [min(xs),min(ys),min(w,max(xs)+patch),min(h,max(ys)+patch)]


def compare(reference,candidate,box):
    x0,y0,x1,y1=box
    if candidate.shape!=(y1-y0,x1-x0):raise ValueError('Incorrect regional shape')
    differences=0;values=0
    for y in range(y1-y0):
        a=reference.row(0,y+y0,x0,x1);b=candidate.row(0,y,0,x1-x0)
        differences+=sum(x!=z for x,z in zip(a,b));values+=len(a)
    return differences,values


def check_case(root,case):
    root=root.resolve()
    result_path=base.safe_path(root,case['result']);data=json.loads(result_path.read_text())
    if data['status']!='completed':raise ValueError('Incomplete worker')
    with base.U8Array(base.safe_path(root,case['input'])) as source:
        divisor=1 if case['sampling']==2.4 else 4
        if any(n%divisor for n in source.shape):raise ValueError('Input shape not divisible')
        shape=[n//divisor for n in source.shape]
    if shape!=data['input_shape']:raise ValueError('Incorrect transformed shape')
    h,w=shape[-2:];patch=256 if case['sampling']==2.4 else 64
    requests={'centre':[144,144,208,208]} if case['sampling']==2.4 else {'edge':[0,0,16,16],'centre':[36,36,52,52],'large':[16,16,w-16,h-16]}
    if data['sample']!=case['sample'] or data['sampling_um']!=case['sampling'] or data['reverse']!=case['reverse']:
        raise ValueError('Worker configuration differs from case')
    if data['input_sha256']!=base.digest(base.safe_path(root,case['input'])):raise ValueError('Worker input differs')
    if data['checkpoint_sha256']!=case['checkpoint_sha256']:raise ValueError('Checkpoint identity differs')
    for key,path in [('reader_sha256','src/hecate_roi.py'),('runtime_sha256','data/paired-resolution-audit/hecate-runtime-pinned.py')]:
        if data[key]!=base.digest(base.safe_path(root,path)):raise ValueError('Worker implementation differs')
    expected=set();rows={}
    for repeat in range(3):
        expected.add((repeat,'full',None))
        for name in requests:
            for method in ('regional','halo'):expected.add((repeat,method,name))
    for row in data['rows']:
        key=(row['repeat'],row['method'],row['region'])
        if key in rows:raise ValueError('Duplicate measurement')
        rows[key]=row
        if not math.isfinite(row['seconds']) or row['seconds']<=0:raise ValueError('Invalid duration')
        path=result_path.parent/row['output'];path=base.safe_path(root,str(path.relative_to(root)))
        if base.digest(path)!=row['output_sha256']:raise ValueError('Output hash mismatch')
    if set(rows)!=expected:raise ValueError('Missing or unexpected measurement')
    per_region={name:[] for name in requests};counts={'regional_values':0,'halo_values':0,'repeated_full_values':0}
    for repeat in range(3):
        f=rows[repeat,'full',None]
        if f['temporary_accumulator_bytes']!=8*h*w:raise ValueError('Full accumulator count differs')
        with base.U8Array(result_path.parent/f['output']) as full:
            if full.shape!=(h,w):raise ValueError('Incorrect full output shape')
            if repeat:
                with base.U8Array(result_path.parent/rows[0,'full',None]['output']) as original:
                    changed,n=compare(original,full,[0,0,w,h]);counts['repeated_full_values']+=n
                    if changed:raise ValueError('Full-field predictions changed across repeats')
            for name,box in requests.items():
                a=rows[repeat,'regional',name];b=rows[repeat,'halo',name]
                ctx=context((h,w),patch,box)
                for method,row in [('regional',a),('halo',b)]:
                    if row['roi_xyxy']!=box:raise ValueError('Request changed')
                    if row['context_xyxy']!=(ctx if method=='halo' else None):raise ValueError('Context changed')
                    area=box if method=='regional' else ctx
                    if row['temporary_accumulator_bytes']!=8*(area[2]-area[0])*(area[3]-area[1]):raise ValueError('Accumulator geometry differs')
                    with base.U8Array(result_path.parent/row['output']) as candidate:
                        changed,n=compare(full,candidate,box);counts[method+'_values']+=n
                        if changed or changed!=row['different_values']:raise ValueError('Saved prediction differs')
                per_region[name].append({'repeat':repeat,'full_seconds':f['seconds'],'regional_seconds':a['seconds'],'halo_seconds':b['seconds'],
                    'full_over_regional':f['seconds']/a['seconds'],'regional_over_halo':a['seconds']/b['seconds'],
                    'halo_over_regional_accumulator':b['temporary_accumulator_bytes']/a['temporary_accumulator_bytes'],
                    'full_tiles':f['neural_tiles'],'regional_tiles':a['neural_tiles'],'halo_tiles':b['neural_tiles']})
    summarized=[]
    for name,trials in per_region.items():
        stats={key:{'median':statistics.median(t[key] for t in trials),'minimum':min(t[key] for t in trials),'maximum':max(t[key] for t in trials)} for key in trials[0] if key!='repeat'}
        summarized.append({'sample':case['sample'],'sampling':case['sampling'],'region':name,'trials':trials,'statistics':stats})
    return counts,summarized


def verify(root):
    root=root.resolve();original=base.verify(root)
    cases=json.loads(base.safe_path(root,'repeatability/cases.json').read_text())
    if [c['index'] for c in cases]!=list(range(5)):raise ValueError('Five fixed worker cases required')
    totals={'regional_values':0,'halo_values':0,'repeated_full_values':0};rows=[]
    for case in cases:
        counts,items=check_case(root,case);rows.extend(items)
        for key,value in counts.items():totals[key]+=value
    result=json.loads(base.safe_path(root,'repeatability/result.json').read_text())
    if result['rows']!=rows:raise ValueError('Recorded summary differs from independently recomputed arithmetic')
    centre=[r for r in rows if r['region']=='centre'];small=[r for r in rows if r['region']!='large']
    gates={'exact_all_outputs':True,'central_speed_repeats':all(r['statistics']['full_over_regional']['median']>=1.5 for r in centre),
        'small_storage_advantage':all(r['statistics']['halo_over_regional_accumulator']['minimum']>=16 for r in small),
        'small_time_nonregression_vs_halo':all(r['statistics']['regional_over_halo']['median']<=1.25 for r in small)}
    if result['gates']!=gates or result['all_gates_passed']!=all(gates.values()):raise ValueError('Gate evaluation differs')
    return {'status':'passed','original_saved_values':original['compared_values'],'worker_cases':len(cases),'requests':len(rows),'repeats_per_request':3,
        **totals,'gates':gates,'scope':'File integrity, saved output equivalence and independently recomputed recorded timing/storage summaries. No model or timing benchmark was run by this verification command; no ink-truth claim.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,default=HERE);parser.add_argument('--json',action='store_true')
    args=parser.parse_args();r=verify(args.package)
    if args.json:print(json.dumps(r,indent=2))
    else:
        print(f"PASS: {r['worker_cases']} worker cases, {r['requests']} requests × 3 repeats; {r['regional_values']:,} regional and {r['halo_values']:,} context-crop values agree with their full-field references.")
        print(r['scope'])
