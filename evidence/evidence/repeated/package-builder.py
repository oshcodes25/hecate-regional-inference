"""Build a new reviewer edition from the completed registered repeatability study."""
import base64
import hashlib
import html
import json
from pathlib import Path
import shutil
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/hecate-repeatability/continuation-01'
DEST=ROOT/'submissions/hecate-regional-reader-repeated-v3'


def read(p):return json.loads(p.read_text())


def record(p,base):
    data=p.read_bytes();return {'path':str(p.relative_to(base)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def manifest():
    files=[record(p,DEST) for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='MANIFEST.json' and '__pycache__' not in p.parts]
    (DEST/'MANIFEST.json').write_text(json.dumps({'algorithm':'SHA256','self_excluded':True,'files':files},indent=2)+'\n')


def render():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plan=read(RUN/'registered-plan.json');summary=read(RUN/'result.json');payload=[]
    for case in plan['cases']:
        folder=RUN/f"case-{case['index']:02d}";worker=read(folder/'result.json')
        volume=np.load(ROOT/case['input']['path'],allow_pickle=False)
        if case['sampling']==9.6:
            d,h,w=volume.shape;volume=np.rint(volume.reshape(d//4,4,h//4,4,w//4,4).mean(axis=(1,3,5))).astype(np.uint8)
        for name in case['regions']:
            stat=next(r for r in summary['rows'] if r['sample']==case['sample'] and r['sampling']==case['sampling'] and r['region']==name)
            outputs={method:next(r for r in worker['rows'] if r['repeat']==0 and r['method']==method and (method=='full' or r['region']==name)) for method in ['full','regional','halo']}
            x0,y0,x1,y1=outputs['regional']['roi_xyxy'];arrays={method:np.load(folder/r['output'],allow_pickle=False) for method,r in outputs.items()}
            arrays['full']=arrays['full'][y0:y1,x0:x1];arrays['ct']=volume[volume.shape[0]//2,y0:y1,x0:x1]
            payload.append({'label':f"{case['sample']} · {case['sampling']} µm · {name}",'sample':case['sample'],'sampling':case['sampling'],'region':name,
                'roi':[x0,y0,x1,y1],'shape':[y1-y0,x1-x0],'depth':volume.shape[0],
                'field_shape':list(volume.shape[-2:]),'context':outputs['halo']['context_xyxy'],
                'ctfield':base64.b64encode(np.ascontiguousarray(volume[volume.shape[0]//2]).tobytes()).decode(),
                'arrays':{k:base64.b64encode(np.ascontiguousarray(v).tobytes()).decode() for k,v in arrays.items()},
                'statistics':stat['statistics'],'trials':stat['trials'],'accumulator_bytes':{k:v['temporary_accumulator_bytes'] for k,v in outputs.items()}})
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'savefig.facecolor':'white'})
    labels=[r['label'].replace('PHerc','').replace(' · ',' ') for r in payload];y=np.arange(len(labels))
    fig,axes=plt.subplots(1,2,figsize=(12.5,6.7),layout='constrained')
    for ax,key,title,xlabel in [(axes[0],'full_over_regional','Compared with full-field inference','Full-field seconds / regional seconds'),(axes[1],'regional_over_halo','Compared with careful context cropping','Regional seconds / context-crop seconds')]:
        values=np.array([r['statistics'][key]['median'] for r in payload]);low=np.array([r['statistics'][key]['minimum'] for r in payload]);high=np.array([r['statistics'][key]['maximum'] for r in payload])
        ax.errorbar(values,y,xerr=[values-low,high-values],fmt='o',color='#176b58',capsize=3)
        ax.axvline(1,color='#777',linestyle='--',linewidth=1);ax.set_yticks(y,labels);ax.invert_yaxis();ax.set_xlabel(xlabel);ax.set_title(title);ax.spines[['top','right']].set_visible(False)
    fig.suptitle('Three local repeats per request · points = median, bars = observed min–max',fontsize=12)
    fig.savefig(DEST/'repeatability.png',dpi=160,metadata={'Software':'Matplotlib'});plt.close(fig)
    rows=[]
    for r in payload:
        s=r['statistics'];ratio=s['full_over_regional'];halo=s['regional_over_halo'];storage=s['halo_over_regional_accumulator']['median']
        rows.append('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in [r['label'],f"{ratio['median']:.2f}× ({ratio['minimum']:.2f}–{ratio['maximum']:.2f})",f"{halo['median']:.3f} ({halo['minimum']:.3f}–{halo['maximum']:.3f})",f'{storage:.2f}×'])+'</tr>')
    template=(ROOT/'src/templates/hecate_repeated.html').read_text()
    template=template.replace('__PAYLOAD__',json.dumps(payload,separators=(',',':'))).replace('__TABLE__',''.join(rows)).replace('__GATES__','All four registered gates passed.' if summary['all_gates_passed'] else 'Some registered gates failed; inspect the full results before claiming a benefit.')
    (DEST/'START_HERE.html').write_text(template)
    (DEST/'repeatability/view-data.json').write_text(json.dumps(payload,indent=2)+'\n')


def build():
    summary=read(RUN/'result.json');execution=read(RUN/'execution.json');plan=read(RUN/'registered-plan.json')
    if execution['status']!='completed' or len(execution['completed'])!=5:raise ValueError('All fixed cases required')
    if DEST.exists():raise ValueError('New version directory already exists')
    shutil.copytree(ROOT/'submissions/hecate-regional-reader-review-v2',DEST,ignore=shutil.ignore_patterns('__pycache__','MANIFEST.json'))
    (DEST/'START_HERE.html').rename(DEST/'ORIGINAL_WALKTHROUGH.html')
    def copy(source,target):
        out=DEST/target;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,out)
    copy(ROOT/'src/verify_hecate_repeats.py','verify_repeats.py')
    copy(ROOT/'src/rebuild_hecate_repeated_view.py','rebuild_view.py')
    test=(ROOT/'tests/test_hecate_repeat_verifier.py').read_text().replace("str(Path(__file__).resolve().parents[1]/'src')","str(Path(__file__).resolve().parents[1])").replace('from verify_hecate_repeats import','from verify_repeats import')
    (DEST/'tests/test_repeat_verifier.py').write_text(test)
    copy(ROOT/'src/package_hecate_repeated.py','evidence/repeated/package-builder.py')
    copy(ROOT/'src/templates/hecate_repeated.html','evidence/repeated/page-template.html')
    copy(ROOT/'src/resume_hecate_repeatability.py','evidence/repeated/continuation-launcher.py')
    for name in ['registered-plan.json','execution.json','result.json','amendment.json','power-observations.jsonl']:
        copy(RUN/name,'repeatability/'+name)
    for name in ['failure.json','execution.json','case-01.log']:
        copy(RUN.parent/name,'repeatability/interruption/'+name)
    cases=[]
    for case in plan['cases']:
        folder=RUN/f"case-{case['index']:02d}"
        for file in sorted(folder.iterdir()):
            if file.is_file():copy(file,'repeatability/outputs/'+folder.name+'/'+file.name)
        cases.append({'index':case['index'],'sample':case['sample'],'sampling':case['sampling'],'reverse':case['reverse'],
            'input':'inputs/'+case['sample']+'.npy','checkpoint_sha256':case['checkpoint']['sha256'],
            'result':'repeatability/outputs/'+folder.name+'/result.json'})
    (DEST/'repeatability/cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    # Preserve the historical v2 notes as dated records, replacing the active guides.
    for name in ['README.md','SUBMISSION.md','CHANGES.md']:(DEST/name).rename(DEST/('V2_'+name))
    (DEST/'repeatability/README.md').rename(DEST/'repeatability/PRE_EXECUTION_README.md')
    small=[r for r in summary['rows'] if r['region']!='large'];central=[r for r in summary['rows'] if r['region']=='centre']
    speed=[r['statistics']['full_over_regional']['median'] for r in central];nonreg=[r['statistics']['regional_over_halo']['median'] for r in small]
    gate_text='All four registered gates passed.' if summary['all_gates_passed'] else 'The full registered gate set did not pass; see result.json for the failed gates.'
    overview=f'''# Hecate regional reader — repeated comparison, v3

Open **START_HERE.html**. The completed comparison includes 11 requests across three existing CT fields, with three balanced-order repeats. Both regional inference and carefully aligned context cropping are compared with the original full-field prediction. {gate_text}

The five central requests have median full/regional time ratios of **{min(speed):.2f}–{max(speed):.2f}×**. Small-request regional/context-crop time ratios are **{min(nonreg):.3f}–{max(nonreg):.3f}** (below 1 means regional was quicker). Both small-region methods evaluate the same contributing tiles. Do not claim a novel neural-work reduction or clear speed superiority over careful cropping. The additional contribution is automatic original-grid handling, the existing batch/3D API, and smaller temporary output accumulators. For the tested small requests these arrays are 16–36× smaller than in the context-crop alternative. These are disk-backed blending arrays, not total model RAM.

## Verify saved results — no installation

```sh
python3 verify_repeats.py
```

Python 3.10+ and the standard library are sufficient. This checks all package file hashes, the original eight-case saved result, the new saved outputs, repeated full-field predictions and independently recomputed timing/storage summaries. It does not rerun the model, independently measure time, or establish ink truth.

## Rerun the model

Use a separate Python 3.12 environment and install `requirements-review.lock`. Download the corresponding Hecate checkpoint from the pinned revision linked in V2_README.md; hashes are recorded. Then use the portable command and fixed five-case table in `repeatability/README.md`. Every worker writes a new output directory. No automatic model download is performed.

For a short rerun of the original demonstration:

```sh
python reproduce.py --rerun --case 0 --models models --output my-rerun
python -m unittest discover -s tests -v
```

The main software remains `src/hecate_roi.py`. V2_README.md contains its full CLI/API instructions; it is retained as a dated historical document. The original E079 scientific report is REPORT.html. ORIGINAL_WALKTHROUGH.html and V2_SUBMISSION.md preserve the earlier explanation and its then-pending benchmark status. The current completed result is this edition's START_HERE.html and repeatability/result.json.

To rebuild and check the saved visual report without model inference, use the recorded NumPy 2.2.6 / Matplotlib 3.10.7 environment and run `python rebuild_view.py`. This regenerates the HTML and scientific figure in a temporary folder and compares their exact bytes. It leaves the delivered package untouched.

## Scope

CPU float32, four threads, unchanged Hecate weights, batch size one, three balanced repeats, one excluded warmup per worker. The new study uses two fine central requests and edge/centre/large requests on three coarse fields. All are existing exposed fields; there is no new ink-accuracy or letter claim. No GPU, cloud-I/O, independent machine or user-time benefit is established. Larger requests can require every original tile. Three repeats measure local variability; they do not justify a population confidence interval. Coarse requests share a full-field timing within each repetition and are dependent observations.

One power interruption terminated an incomplete attempt on the second case before any prediction was saved. The first case was preserved exactly; a reviewed operational amendment reran only the remaining cases under unchanged scientific settings. The interrupted attempt and its resource use remain in the logs and aggregate budget.

The global-grid/context principle predates this work (villa PR #1247). Existing Hecate speed and shared-feature work is credited in the original source audit. The package is private and has not been submitted or published. Code is MIT; data retain the terms in DATA-NOTICE.md.
'''
    (DEST/'README.md').write_text(overview)
    repeat_readme=(DEST/'repeatability/PRE_EXECUTION_README.md').read_text()
    repeat_readme=repeat_readme.replace('# Registered follow-up — not yet executed','# Completed registered repeatability study')
    first='The plan is frozen before measurement. `execution-at-packaging.json` records zero attempts, waiting for AC power. The original workspace launcher enforces AC power, an open lid, time and resource limits; it is not a background job.'
    repeat_readme=repeat_readme.replace(first,'All five fixed cases completed. The first case finished before a power interruption stopped the second. The interrupted attempt saved no predictions. A reviewed operational amendment preserved it, reused the completed first case byte-for-byte and reran only the remaining cases under the unchanged scientific settings. Original and continued execution records are included, and the original aggregate resource cap includes the interrupted attempt. `execution-at-packaging.json` is the preserved earlier v2 waiting state. Run `python3 verify_repeats.py` from the package root to verify the completed saved results and recorded arithmetic.')
    (DEST/'repeatability/README.md').write_text(repeat_readme)
    (DEST/'CHANGES.md').write_text('''# Changes in v3

The already registered repeated model comparison has now executed in the clean environment. All outputs and trials are included, with the careful aligned-context-crop baseline and edge/large sensitivity cases. The new standard-library verifier independently compares saved values and recomputes every reported median/range and registered gate. The new viewer uses the actual newly generated outputs and discloses the stronger baseline.

No model weights, inference implementation, thresholds or registered scientific settings changed. Versions 1 and 2 remain frozen in the original workspace. Historical v2 guides and its unexecuted-state record are preserved with explicit names; the active guides describe v3.
''')
    (DEST/'SUBMISSION.md').write_text(f'''# Context-preserving regional inference for Hecate

Author: Oisin McGlone · oisinmcglone25@gmail.com  
Category: Progress Prize, reading software  
Status: Private draft; no submission or publication made.

Researchers inspecting a small region can change Hecate's output by cropping its input without preserving the original context and tile grid. This regional API accepts the original array and desired output coordinates, preserves the original contributing tile/batch contexts and blending, and limits temporary accumulation to the requested output.

The original eight-case experiment matched all 541,184 saved regional values across two fields, fine/coarse resolutions, 2D/3D outputs and batch/depth configurations. A separate preregistered follow-up now compares full-field, regional and carefully aligned context-crop inference for 11 fixed requests on three existing fields, with three balanced-order repeats in a fresh pinned environment. {gate_text} Every trial and saved output is supplied.

For the five central requests, median full/regional time ratios are {min(speed):.2f}–{max(speed):.2f}×. The important competing context-crop method also reduces the neural tile count. We therefore claim no invention of that principle or clear speed superiority over careful cropping. The additional contribution is a reusable Hecate regional interface, preservation of original batch/depth behavior, smaller temporary output accumulators and a reproducible comparison. Small requests use 16–36× less temporary accumulation than the aligned-crop baseline; total model-memory reduction is not claimed. Large requests are included and may need all tiles.

The package includes an offline interactive explanation, real bounded CT inputs, all measured outputs, fixed plans, source/runtime revisions, checkpoint hashes, tests and a standard-library-only saved-result verifier. `python3 verify_repeats.py` checks the evidence; the separate portable worker commands perform fresh inference. Local Zarr v2 input loading and CLI scheduling have also been checked. No paid compute or training was used.

The global-grid principle in villa PR #1247 is the closest credited predecessor; existing Hecate fast-path and paired-feature work is also credited. This is correctness/efficiency software, not new verified writing. The reference is software output on small supplied fields, not ink ground truth. The fields were previously exposed; fresh reading validation, independent hardware, GPU/cloud performance and community adoption are not established.

Review START_HERE.html, README.md, src/hecate_roi.py, repeatability/result.json and the included plans. Code is MIT with upstream attribution; data and derived views retain their source terms. The current Progress Prize rules allow private submission and require permissive public release to accept an award. The published next deadline is 31 October 2026 at 23:59 Pacific; acceptance and award size are for the organizers to decide.
''')
    render();manifest();print(DEST)


if __name__=='__main__':
    import sys
    {'build':build,'render':render,'manifest':manifest}[sys.argv[1]]()
