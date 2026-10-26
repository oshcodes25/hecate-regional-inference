"""Create a separately versioned reviewer package without changing E079."""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'submissions/hecate-context-preserving-roi-20261026'
DEST=ROOT/'submissions/hecate-regional-reader-review-v2'
RUN=ROOT/'runs/hecate-submission-strengthening'


def record(path,base):
    data=path.read_bytes()
    return {'path':str(path.relative_to(base)),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def manifest():
    files=[record(p,DEST) for p in sorted(DEST.rglob('*')) if p.is_file() and p.name!='MANIFEST.json' and '__pycache__' not in p.parts]
    (DEST/'MANIFEST.json').write_text(json.dumps({'algorithm':'SHA256','self_excluded':True,'files':files},indent=2)+'\n')


def render():
    result=json.loads((SOURCE/'evidence/result.json').read_text());payload=[]
    for row in result['cases'][:2]:
        c=row['case'];volume=np.load(ROOT/c['input']['path'],allow_pickle=False,mmap_mode='r')
        x0,y0,x1,y1=c['roi_xyxy'];out={k:np.load(ROOT/f['path'],allow_pickle=False) for k,f in row['outputs'].items()}
        def encoded(a):return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()
        h,w=volume.shape[-2:]
        def starts(n):
            values=list(range(0,n-256+1,128))
            if values[-1]!=n-256:values.append(n-256)
            return values
        payload.append({'sample':c['sample'],'width':w,'height':h,'ct':encoded(volume[32]),
            'reference':encoded(out['full'][y0:y1,x0:x1]),'naive':encoded(out['naive']),'regional':encoded(out['roi']),
            'full_origins':[[y,x] for y in starts(h) for x in starts(w)],
            'regional_origins':[o for g in row['measurements']['roi']['detail']['groups'] for o in g['origins']],
            'naive_changed':row['naive_difference']['differing_values'],
            'measurements':{label:{'seconds':row['measurements'][key]['seconds'],'tiles':row['measurements'][key]['neural_tiles']} for label,key in (('full','full'),('naive','naive'),('regional','roi'))}})
    template=(ROOT/'src/templates/hecate_walkthrough.html').read_text()
    (DEST/'START_HERE.html').write_text(template.replace('__PAYLOAD__',json.dumps(payload,separators=(',',':'))))
    (DEST/'evidence/walkthrough-source.json').write_text(json.dumps({'source':'E079 frozen result and input/output arrays','ct_plane_zero_based':32,'values':'Raw uint8 codes, no learned or generative edits','model_execution_in_browser':False,'sample_cases':[0,1]},indent=2)+'\n')


def build():
    if DEST.exists():raise ValueError('Version directory already exists')
    shutil.copytree(SOURCE,DEST,ignore=shutil.ignore_patterns('__pycache__','MANIFEST.json'))
    def copy(source,target):
        out=DEST/target;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/source,out)
    copy('src/verify_hecate_roi_standard.py','verify.py')
    test=(ROOT/'tests/test_hecate_roi_standard_verifier.py').read_text().replace("str(Path(__file__).resolve().parents[1]/'src')","str(Path(__file__).resolve().parents[1])").replace('from verify_hecate_roi_standard import','from verify import')
    (DEST/'tests/test_standard_verifier.py').write_text(test)
    for name in ('requirements-review.lock','wheel-manifest.json','environment-plan.json','fresh-freeze.txt','fresh-install.log','fresh-dependency-check.log','fresh-verification.log','fresh-tests.log','tests-before-registration.log','stdlib-verification.json'):
        copy('runs/hecate-submission-strengthening/'+name,'evidence/review/'+name)
    copy('runs/hecate-submission-strengthening/requirements-review.lock','requirements-review.lock')
    copy('runs/hecate-repeatability/registered-plan.json','repeatability/registered-plan.json')
    copy('runs/hecate-repeatability/execution.json','repeatability/execution-at-packaging.json')
    copy('src/measure_hecate_regions.py','repeatability/measure.py')
    copy('data/hecate-fine-projection/prepared/pherc0841-development/ct.npy','inputs/PHerc0841.npy')
    copy('src/package_hecate_review.py','evidence/review/package-builder.py')
    copy('src/templates/hecate_walkthrough.html','evidence/review/walkthrough-template.html')
    original=(SOURCE/'README.md').read_text()
    original=original.replace('Open `REPORT.html` in a browser.','Open **`START_HERE.html`** for the short visual walkthrough, then `REPORT.html` for the complete eight-case scientific viewer.')
    original=original.replace('Python 3.10+ and NumPy are sufficient:\n\n```sh\npython -m pip install numpy==2.2.6\npython reproduce.py\n```','Python 3.10+ is sufficient; no third-party package is needed:\n\n```sh\npython3 verify.py\n```')
    original=original.replace('Install `requirements.txt` in a separate virtual environment.','For the exact freshly installed Python 3.12 environment, use `python -m pip install -r requirements-review.lock` in a separate virtual environment. `requirements.txt` retains the minimal direct dependencies. The fresh installation was verified on this same Mac, not a second computer.')
    intro='''# Reviewer edition, version 2

Start with **START_HERE.html**. It uses real saved CT/output arrays to explain the contribution in three steps. Run **python3 verify.py** for the saved-output check without installing any packages. The original E079 scientific viewer, numerical results, source implementation and predictions are preserved.

**New in this edition:** a plain-language walkthrough, a standard-library verifier with tamper-detection tests, a clean virtual-environment installation with all 11 dependency versions and wheel hashes recorded, and a preregistered stronger benchmark. See `CHANGES.md` and `QA-REVIEW.md` for the new work. The inherited `QA.md` describes the original package, not additional checks of this edition.

**Important remaining comparison:** a carefully aligned surrounding-context crop may match our reduction in neural work. This was not measured in E079. The separately registered three-repeat study is **waiting for AC power and has not executed**. Its plan and portable worker are included under `repeatability/`. Do not read the older one-trial timings as evidence of superiority over this stronger alternative.

'''
    (DEST/'README.md').write_text(intro+original)
    submission=(SOURCE/'SUBMISSION.md').read_text()
    submission=submission.replace('**Status:** Private draft, ready for owner review; no submission or publication made.','**Status:** Private reviewer edition v2; no submission or publication made. Repeated performance validation against careful context cropping remains pending.')
    submission=submission.replace('The submission includes an offline interactive CT/output viewer,','The submission includes a short visual walkthrough, a standard-library-only saved-output verifier, a clean-installation record, an offline interactive CT/output viewer,')
    submission=submission.replace('Files to review first: `REPORT.html`,','Files to review first: `START_HERE.html`, `REPORT.html`,')
    submission=submission.replace('Run `python reproduce.py` to verify','Run `python3 verify.py` to verify')
    submission+='''
## Stronger comparison being prepared

A carefully selected crop retaining the original aligned context is an important alternative to our regional API. It may match the reduced model workload, while allocating larger temporary blending arrays. We explicitly do not claim a speed advantage over that alternative without measurements. The next registered study fixes three balanced-order repeats across two fine-resolution centre cases and edge/centre/large requests in three coarse-resolution specimens. It is waiting for AC power; no result from that study is included in the current claim.

The fresh environment installed all 11 pinned dependency packages from recorded binary wheels, passed `pip check`, all ten original portable tests and the 541,184-value saved-output verification. This establishes a clean installation on the same laptop. It does not establish independent hardware replication or a fresh neural-model rerun.
'''
    (DEST/'SUBMISSION.md').write_text(submission)
    (DEST/'CHANGES.md').write_text('''# Changes from the original E079 package

- Added START_HERE.html: actual CT and saved predictions, three explanatory steps, both primary specimens, linked display brightness, precise scope and practical uses.
- Added verify.py: Python standard library only, file hashes, strict uint8 NPY parsing, all 541,184 saved values and the naïve control counts. Four targeted tests include a deliberately altered output and an escaping path.
- Installed 11 exact dependency versions into a newly created Python 3.12.15 virtual environment. Wheel hashes, install/dependency logs and ten passing portable tests are retained. This was performed on the same Mac M2 Pro.
- Registered a repeated comparison against full-field inference and independently selected surrounding-context crops before running it. All cases, comparisons, gates, failure policy and resource limits are recorded. It is waiting for power, with zero model attempts.
- Included the third already available CT input needed by the new benchmark, its standalone measurement worker and commands. No new scans were downloaded.

The E079 model, inference implementation, eight-case settings, labels, arrays, measurements, detailed report and predecessor credits are unchanged. The new package is a separate directory; the original package and archive remain frozen.

This edition does not claim additional performance measurements, improved ink accuracy, GPU validation, community adoption or a second-machine replication.
''')
    (DEST/'repeatability/README.md').write_text('''# Registered follow-up — not yet executed

The plan is frozen before measurement. `execution-at-packaging.json` records zero attempts, waiting for AC power. The original workspace launcher enforces AC power, an open lid, time and resource limits; it is not a background job.

The portable `measure.py` worker requires only Python, NumPy and Torch. It compares the original full-field runtime, our frozen regional API and independently selected aligned surrounding-context crops. It uses unchanged weights, four CPU threads, float32, batch size one, one excluded warmup, and three balanced-order repeats. All outputs and every time are saved; a differing or slow case must not be dropped. Large-region cases are sensitivity tests.

From the package directory, after installing `requirements-review.lock` and obtaining the checkpoints described in the main README, the first registered worker command is:

```sh
python -I repeatability/measure.py \\
  --reader src/hecate_roi.py \\
  --runtime data/paired-resolution-audit/hecate-runtime-pinned.py \\
  --checkpoint models/hecate_2.4um.pth \\
  --input inputs/PHerc0009B.npy --sample PHerc0009B \\
  --sampling 2.4 --seconds 600 --output repeated-case-00
```

Use AC power, keep the computer awake, and do not run competing compute jobs during timings. No automatic downloads are performed. Existing output directories are rejected. Model hashes are in cases.json and the original registered plan; verify them before an independent run.

The complete fixed worker list is below. All use the same reader/runtime arguments. The first two use a 600-second worker cap, the last three 300 seconds. Total active worker cap is 2400 seconds; maximum RSS is 8 GiB. Every output is 2D. Coarse inputs are formed by fixed 4×4×4 averaging and rounding inside the worker.

| Index | Input | Sampling µm | Depth order | Regions |
|---|---|---:|---|---|
| 0 | PHerc0009B.npy | 2.4 | forward | centre |
| 1 | PHerc0500P2.npy | 2.4 | forward | centre |
| 2 | PHerc0841.npy | 9.6 | forward | edge, centre, large |
| 3 | PHerc0009B.npy | 9.6 | forward | edge, centre, large |
| 4 | PHerc0500P2.npy | 9.6 | reverse (`--reverse`) | edge, centre, large |

These are previously exposed fields, not new reading-validation regions. No labels are used. Exact agreement with a software reference does not demonstrate physical ink accuracy. Full-field reference times in the coarse cases are reused across the three requests within each repeat; those speed ratios are dependent observations. Three repeats characterize local variability, not a population confidence interval.

The strongest new claim is conditional: if the aligned crop matches compute/time, the added contribution must be limited to automatic handling, original batching and output accumulator savings. Do not describe context preservation as an invention of this work; villa PR #1247 is a credited predecessor.
''')
    notice=DEST/'DATA-NOTICE.md'
    notice.write_text(notice.read_text().replace('Source records identify the two surface volumes,','Source records identify the three supplied surface volumes (PHerc0841, PHerc0009B and PHerc0500P2),')+'\nThis reviewer edition adds the already qualified PHerc0841 CT input for the pending repeatability benchmark. Its source records are retained in evidence/qualified-source-inputs.json and evidence/qualified-input-preparation.json. No new PHerc0841 inference result is claimed.\n')
    render();manifest();print(DEST)


if __name__=='__main__':
    {'build':build,'render':render,'manifest':manifest}[sys.argv[1]]()
