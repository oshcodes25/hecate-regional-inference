"""E079: registered real-CT equivalence and resource test of Hecate ROI inference."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
import hecate_projection as core
import hecate_roi as roi

ROOT=core.ROOT
RUN=ROOT/'runs/hecate-roi'


def read(path):return json.loads(Path(path).read_text())


def register():
    RUN.mkdir(parents=True,exist_ok=True)
    if (RUN/'registered-plan.json').exists():raise ValueError('Already registered')
    source=read(ROOT/'runs/hecate-fine-projection/preparation-result.json')
    source_regions=read(ROOT/'runs/hecate-fine-projection/source-inputs.json')['regions']
    cases=[]
    for spacing in (2.4,9.6):
        for three_d in (False,True):
            for index in (1,2):
                ref=source['regions'][index];name=source_regions[index]['region']['sample']
                cases.append({'index':len(cases),'sample':name,'input':ref['files']['ct'],
                    'source_geometry':source_regions[index]['region'],
                    'sampling_um':spacing,'three_d':three_d,'reverse':three_d if index==1 else spacing==9.6,
                    'roi_xyxy':[144,144,208,208] if spacing==2.4 else [36,36,52,52],
                    'batch_size':3 if spacing==9.6 and index==2 else 1,
                    'order':['full','roi','naive'] if index==1 else ['roi','full','naive'],
                    'checkpoint':core.file_record(ROOT/('data/models/hecate/hecate_'+str(spacing)+'um.pth'))})
    plan={'registered_at':datetime.now(timezone.utc).isoformat(),'cases':cases,
        'question':'Can a Hecate regional API reproduce the corresponding full-surface uint8 output exactly while evaluating fewer tiles and using smaller temporary accumulators?',
        'baseline':'Unmodified pinned Hecate predict over the entire supplied real CT field, then crop the saved output to the requested ROI.',
        'comparison':'Keep the full input grid, complete original batch groups, full tile contexts, support, arithmetic order and Hann weights; evaluate only batches intersecting the ROI. Control: physically crop the input before unmodified predict.',
        'predecessors':[
            'ScrollPrize/villa PR #1247 already fixes global patch-grid provenance for the surface-segmentation --bbox pipeline. The principle is not original; this work applies and verifies it for the separate Hecate runtime.',
            'ArcheyChen/vesuvius-eligible-scouting c73d0dd documents a faster 2D Hecate pipeline and the accuracy cost of increased stride; no regional API or 3D support in the inspected fast implementation.',
            'Hecate HF discussion #1 already proposes shared 2D/3D features. That contribution is excluded here.'],
        'competing_explanations':['Naive input cropping changes context/grid and therefore predictions; preserved full-grid contexts eliminate the discrepancy.',
            'Cropping has negligible effect or implementation arithmetic/batching differences prevent exact equivalence.',
            'Correctness requires so many surrounding tiles that there is no practical time or temporary-storage saving.'],
        'metric':'All uint8 output pixels/voxels must match the full-field crop exactly. Record naive discrepancy, calls, input voxels read, temporary accumulator bytes, end-to-end predict wall time and peak process RSS. No reference-ink metrics or threshold fitting.',
        'success_condition':'Exact output equality in all eight real cases and all synthetic edge/batch tests. In both primary fine-resolution 2D cases, at least 50% fewer neural tiles, at least 4x smaller temporary accumulators, and geometric-mean measured full/ROI wall-time ratio >=1.5. At least one primary naive-crop control must disagree on >=1% of saved ROI pixels.',
        'stop_condition':'Preserve a failed registered run. Do not tune ROI, stride, output precision, model or data selection after results. A code defect requires a separately recorded repair and fresh verification, never overwriting failed evidence.',
        'split':'Two physically distinct existing real CT fields from PHerc9B and PHerc500P2. They are previously exposed research fields, NOT fresh ink-discovery validation. Geometry-only ROI selection was fixed before this software benchmark. No reserved reading-final regions or labels are used.',
        'scope':'Software correctness and efficiency only. The full-surface prediction is an implementation reference, not ground-truth ink. Does not establish better ink recall, a new detector, new text or independent checkpoint generalization.',
        'preparation':'Fine inputs use qualified E040 2.4um arrays unchanged. For 9.6um tests only, average each nonoverlapping 4x4x4 block and round to uint8; input dimensions are divisible by4. This is a fixed software-test input transform, not a proposed reading improvement.',
        'timing':'Four CPU threads, deterministic fp32, model load excluded, one full-context tile warmup excluded. Fixed balanced full/ROI order across specimens; one measured run per case. Report individual values without claiming a general hardware speed guarantee.',
        'resources':{'worker_seconds':330,'total_worker_seconds':2400,'RSS_bytes':8589934592,'output_bytes':201326592,'threads':4,'paid_cost':0,'downloads':0,'fits':0},
        'operational':'Check open lid and AC or >=15% battery before each case. Preserve completed cases and any interruption. This threshold is an execution safeguard, not a user approval requirement.',
        'files':[core.file_record(ROOT/name) for name in ('src/hecate_roi.py','src/benchmark_hecate_roi.py',
            'tests/test_hecate_roi.py','src/hecate_projection.py','src/resume_hecate_broad_projection.py',
            'src/run_hecate_broad_projection.py','data/paired-resolution-audit/hecate-runtime-pinned.py',
            'runs/hecate-roi/tests-main.log','runs/hecate-roi/tests-torch.log')]}
    core.freeze(RUN/'registered-plan.json',plan)
    e={'id':'hecate-roi-20261026','hypothesis_id':'H02','status':'ready','registered_before_execution':True,
        **{k:plan[k] for k in ('question','baseline','comparison','metric','success_condition','stop_condition','split')},
        'dataset':'Two existing qualified physical CT fields, resampled to two supported Hecate resolutions; no labels.',
        'checkpoint_provenance':plan['scope'],'resource_cap':str(plan['resources']),
        'command':'.venv/bin/python src/benchmark_hecate_roi.py launch\n.venv/bin/python src/benchmark_hecate_roi.py audit',
        'environment':'macOS M2 Pro; .venv-ink Torch2.8.0, CPU fp32, four threads; no paid resources.',
        'code_revision':'Plan SHA256 '+core.sha(RUN/'registered-plan.json'),'seeds':[20261026], 'deterministic':True,
        'metrics':{},'artifacts':[core.file_record(RUN/'registered-plan.json'),*plan['files']]}
    core.freeze(ROOT/'experiments/hecate-roi-20261026.json',e)
    print('Registered',core.sha(RUN/'registered-plan.json'))


def plan():
    p=read(RUN/'registered-plan.json')
    for f in p['files']:core.verify(f)
    return p


def worker(index):
    import torch
    p=plan();case=p['cases'][index];folder=RUN/f'case-{index:02d}'
    folder.mkdir(exist_ok=False)
    started=time.monotonic()
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    torch.manual_seed(20261026);torch.use_deterministic_algorithms(True)
    runtime=roi.load_runtime(ROOT/'data/paired-resolution-audit/hecate-runtime-pinned.py')
    volume=np.load(core.verify(case['input']),allow_pickle=False)
    if case['sampling_um']==9.6:
        z,h,w=volume.shape
        if z%4 or h%4 or w%4:raise ValueError('Input must divide into exact4voxel blocks')
        volume=np.rint(volume.reshape(z//4,4,h//4,4,w//4,4).mean(axis=(1,3,5))).astype(np.uint8)
    model=runtime.load_model(core.verify(case['checkpoint']),'cpu')
    calls={'tiles':0,'batches':0};original=model.features_logits
    def count(image):
        calls['tiles']+=len(image);calls['batches']+=1
        return original(image)
    model.features_logits=count
    d,pw,_=model.patch_size
    with torch.inference_mode():
        image=torch.from_numpy(volume[:d,:pw,:pw].astype(np.float32)[None,None]/np.float32(model.divisor))
        model.forward_3d(image) if case['three_d'] else model(image)
    del image
    x0,y0,x1,y1=case['roi_xyxy'];outputs={};measurements={}
    for name in case['order']:
        calls.update(tiles=0,batches=0)
        local=volume[:,y0:y1,x0:x1] if name=='naive' else volume
        shape=((volume.shape[0],) if case['three_d'] else ())+(local.shape[-2:] if name!='roi' else (y1-y0,x1-x0))
        output=np.zeros(shape,np.uint8);began=time.perf_counter()
        with torch.inference_mode():
            if name=='roi':
                detail=roi.predict_roi(model,volume,output,case['roi_xyxy'],case['reverse'],batch_size=case['batch_size'],three_d=case['three_d'])
            else:
                runtime.predict(model,local,output,case['reverse'],batch_size=case['batch_size'],three_d=case['three_d'])
                detail={}
        elapsed=time.perf_counter()-began
        path=folder/(name+'.npy');np.save(path,output,allow_pickle=False);outputs[name]=core.file_record(path)
        measurements[name]={'seconds':elapsed,'neural_tiles':calls['tiles'],'neural_batches':calls['batches'],'detail':detail}
        if time.monotonic()-started>p['resources']['worker_seconds'] or core.peak_rss_bytes()>p['resources']['RSS_bytes']:
            raise RuntimeError('Worker resource cap exceeded')
    full=np.load(core.verify(outputs['full']),mmap_mode='r',allow_pickle=False)[...,y0:y1,x0:x1]
    regional=np.load(core.verify(outputs['roi']),mmap_mode='r',allow_pickle=False)
    naive=np.load(core.verify(outputs['naive']),mmap_mode='r',allow_pickle=False)
    dif=lambda a:{'differing_values':int(np.count_nonzero(a!=full)),
        'fraction_different':float(np.mean(a!=full)),
        'maximum_code_error':int(np.abs(a.astype(np.int16)-full.astype(np.int16)).max()),
        'mean_absolute_code_error':float(np.abs(a.astype(np.int16)-full.astype(np.int16)).mean())}
    core.freeze(folder/'result.json',{'status':'completed','case':case,'input_shape':list(volume.shape),
        'measurements':measurements,'outputs':outputs,'regional_difference':dif(regional),'naive_difference':dif(naive),
        'full_over_roi_seconds':measurements['full']['seconds']/measurements['roi']['seconds'],
        'temporary_accumulator_reduction':float(volume.shape[-2]*volume.shape[-1]/((y1-y0)*(x1-x0))),
        'elapsed_seconds':time.monotonic()-started,'peak_RSS_bytes':core.peak_rss_bytes()})
    print('Completed case',index,flush=True)


def launch():
    import resume_hecate_broad_projection as power_guard
    p=plan();record_path=RUN/'execution.json'
    if (RUN/'failure.json').exists():raise ValueError('Failure requires review; do not retry')
    execution=read(record_path) if record_path.exists() else {'completed':[],'attempts':[],'worker_seconds':0.}
    wake=subprocess.Popen(['caffeinate','-i','-w',str(__import__('os').getpid())])
    try:
        for case in p['cases']:
            i=case['index']
            if i in execution['completed']:continue
            power=power_guard.power()
            permitted=power_guard.may_start(power,minimum=15)
            if not permitted:
                execution['status']='waiting_for_awake_power';execution['last_power']=power
                core.save(record_path,execution);print(json.dumps(execution));return
            began=time.monotonic();command=[str(ROOT/'.venv-ink/bin/python'),'-u',str(Path(__file__)),'worker','--case',str(i)]
            with (RUN/f'case-{i:02d}.log').open('x') as log:
                process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
                try:code=process.wait(timeout=p['resources']['worker_seconds'])
                except subprocess.TimeoutExpired:
                    process.terminate();process.wait(timeout=15);code=-15
            seconds=time.monotonic()-began
            execution['worker_seconds']+=seconds
            execution['attempts'].append({'case':i,'command':command,'exit_code':code,'seconds':seconds,'initial_power':power})
            if code or not (RUN/f'case-{i:02d}'/'result.json').exists():
                execution['status']='failed';core.save(record_path,execution);core.freeze(RUN/'failure.json',execution['attempts'][-1]);raise RuntimeError('Worker failed; evidence preserved')
            execution['completed'].append(i);execution['status']='in_progress';core.save(record_path,execution)
            print('Qualified completed case',i,flush=True)
            if execution['worker_seconds']>p['resources']['total_worker_seconds']:raise RuntimeError('Total worker cap exceeded')
        execution['status']='completed';core.save(record_path,execution)
    finally:wake.terminate();wake.wait()


def audit():
    p=plan();rows=[]
    if read(RUN/'execution.json')['status']!='completed':raise ValueError('All eight cases required')
    for case in p['cases']:
        row=read(RUN/f"case-{case['index']:02d}"/'result.json');x0,y0,x1,y1=case['roi_xyxy']
        ref=np.load(core.verify(row['outputs']['full']),allow_pickle=False)[...,y0:y1,x0:x1]
        candidate=np.load(core.verify(row['outputs']['roi']),allow_pickle=False)
        naive=np.load(core.verify(row['outputs']['naive']),allow_pickle=False)
        for a,k in ((candidate,'regional_difference'),(naive,'naive_difference')):
            count=sum(int(v!=w) for v,w in zip(a.flat,ref.flat))
            if count!=row[k]['differing_values']:raise ValueError('Independent count mismatch')
        if row['measurements']['roi']['neural_tiles']!=row['measurements']['roi']['detail']['neural_tiles']:
            raise ValueError('Independent model call counter disagrees')
        rows.append(row)
    primary=[r for r in rows if r['case']['sampling_um']==2.4 and not r['case']['three_d']]
    geometric_speed=float(np.exp(np.mean(np.log([r['full_over_roi_seconds'] for r in primary]))))
    gates={'exact_all_cases':all(r['regional_difference']['differing_values']==0 for r in rows),
        'half_neural_work_primary':all(r['measurements']['roi']['neural_tiles']<=r['measurements']['full']['neural_tiles']/2 for r in primary),
        'temporary_reduction_primary':all(r['temporary_accumulator_reduction']>=4 for r in primary),
        'wall_time_primary':geometric_speed>=1.5,
        'naive_discrepancy_primary':any(r['naive_difference']['fraction_different']>=.01 for r in primary)}
    if sum(x.stat().st_size for x in RUN.rglob('*') if x.is_file())>p['resources']['output_bytes']:raise RuntimeError('Output cap exceeded')
    result={'status':'completed','cases':rows,'gates':gates,'all_gates_passed':all(gates.values()),
        'primary_geometric_mean_speedup':geometric_speed,'plan_sha256':core.sha(RUN/'registered-plan.json'),
        'scope':p['scope'],'validation_role':p['split']}
    core.freeze(RUN/'result.json',result);print(json.dumps(gates),geometric_speed)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('register','worker','launch','audit'));parser.add_argument('--case',type=int)
    args=parser.parse_args()
    worker(args.case) if args.stage=='worker' else globals()[args.stage]()
