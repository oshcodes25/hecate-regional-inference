"""Check local Zarr v2 loading and CLI planning; no model inference."""
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np
import zarr

ROOT=Path(__file__).resolve().parents[1]
PACKAGE=ROOT/'submissions/hecate-regional-reader-review-v2'
OUT=ROOT/'runs/hecate-submission-strengthening/zarr-input-check.json'


def main():
    if OUT.exists():raise ValueError('Preserve the existing check')
    source=PACKAGE/'inputs/PHerc0009B.npy';volume=np.load(source,allow_pickle=False,mmap_mode='r')
    base=[sys.executable,'-I',str(PACKAGE/'src/hecate_roi.py'),'--runtime',str(PACKAGE/'data/paired-resolution-audit/hecate-runtime-pinned.py'),
        '--spacing-um','2.4','--roi','144','144','208','208','--dry-run']
    with tempfile.TemporaryDirectory(prefix='hecate-zarr-input-') as folder:
        store=Path(folder)/'scan.zarr';group=zarr.open_group(str(store),mode='w')
        data=group.create_dataset('0',data=volume,chunks=(16,128,128),compressor=None)
        compared=0
        for z in range(0,volume.shape[0],16):
            if not np.array_equal(volume[z:z+16],data[z:z+16]):raise ValueError('Stored scan changed')
            compared+=volume[z:z+16].size
        rows=[]
        for label,path in (('npy',source),('zarr',store)):
            command=base+['--input',str(path)]
            run=subprocess.run(command,cwd='/tmp',capture_output=True,text=True,check=True,timeout=30)
            rows.append({'format':label,'command':command,'schedule':json.loads(run.stdout),'stderr':run.stderr})
        if rows[0]['schedule']!=rows[1]['schedule']:raise ValueError('CLI schedules differ')
        if rows[1]['schedule']['scheduled_tiles']!=4:raise ValueError('Unexpected regional schedule')
    result={'status':'passed','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_values_compared':compared,
        'versions':{name:version(name) for name in ('zarr','numcodecs','numpy','torch')},'cases':rows,
        'scope':'Actual local Zarr v2 group/array and packaged CLI dry-run. All source voxels and NPY/Zarr schedules match. No checkpoint loaded, no neural inference, no Zarr v3/cloud-I/O claim. Temporary store removed.'}
    OUT.write_text(json.dumps(result,indent=2)+'\n');print('PASS:',compared,'scan voxels; identical NPY/Zarr CLI schedule')


if __name__=='__main__':main()
