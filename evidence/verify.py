"""Verify the Hecate submission using only Python's standard library.

No downloads, model execution, NumPy, or workspace imports. A successful check
means the saved regional outputs equal the saved full-field reference; it does
not establish physical ink accuracy or reproduce the measured runtime.
"""
import argparse
import ast
import hashlib
import json
import mmap
from pathlib import Path
import struct


def safe_path(root, relative):
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Missing or out-of-package path: '+str(relative))
    return path


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


class U8Array:
    """Strict reader for the C-order uint8 NPY files used by this package."""
    def __init__(self,path):
        self.stream=path.open('rb')
        try:
            if self.stream.read(6)!=b'\x93NUMPY':raise ValueError('Invalid NPY magic')
            version=self.stream.read(2)
            if version==b'\x01\x00':length=struct.unpack('<H',self.stream.read(2))[0]
            elif version in (b'\x02\x00',b'\x03\x00'):length=struct.unpack('<I',self.stream.read(4))[0]
            else:raise ValueError('Unsupported NPY version')
            if length>65536:raise ValueError('Oversized NPY header')
            header=ast.literal_eval(self.stream.read(length).decode('utf-8' if version[0]==3 else 'latin1'))
            if header['descr']!='|u1' or header['fortran_order'] is not False:raise ValueError('Only C-order uint8 is supported')
            self.shape=header['shape']
            if not isinstance(self.shape,tuple) or len(self.shape) not in (2,3) or any(type(n)!=int or n<1 for n in self.shape):
                raise ValueError('Invalid image geometry')
            self.offset=self.stream.tell();size=1
            for n in self.shape:size*=n
            if path.stat().st_size!=self.offset+size:raise ValueError('Truncated or trailing NPY data')
            self.data=mmap.mmap(self.stream.fileno(),0,access=mmap.ACCESS_READ)
        except BaseException:
            self.stream.close();raise

    def row(self,z,y,x0,x1):
        depth,h,w=(1,*self.shape) if len(self.shape)==2 else self.shape
        if not(0<=z<depth and 0<=y<h and 0<=x0<x1<=w):raise ValueError('Row outside image')
        start=self.offset+(z*h+y)*w+x0
        return self.data[start:start+x1-x0]

    def close(self):
        self.data.close();self.stream.close()

    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def verify(root):
    manifest=json.loads((root/'MANIFEST.json').read_text())
    names=set()
    for item in manifest['files']:
        if item['path'] in names:raise ValueError('Duplicate manifest path')
        names.add(item['path']);path=safe_path(root,item['path'])
        if path.stat().st_size!=item['bytes'] or digest(path)!=item['sha256']:
            raise ValueError('File integrity failed: '+item['path'])
    cases=json.loads(safe_path(root,'cases.json').read_text())
    if 'cases.json' not in names:raise ValueError('Case definitions are not covered by manifest')
    checked=0;rows=[]
    for case in cases:
        outputs=case['outputs']
        if not all(p in names for p in outputs.values()):raise ValueError('Unhashed output')
        x0,y0,x1,y1=case['roi_xyxy']
        with U8Array(safe_path(root,outputs['full'])) as full,U8Array(safe_path(root,outputs['roi'])) as regional,U8Array(safe_path(root,outputs['naive'])) as naive:
            expected=(*full.shape[:-2],y1-y0,x1-x0)
            if regional.shape!=expected or naive.shape!=expected:raise ValueError('Output geometry differs')
            depth=full.shape[0] if len(full.shape)==3 else 1
            count=naive_count=0
            for z in range(depth):
                for y in range(y1-y0):
                    reference=full.row(z,y+y0,x0,x1)
                    candidate=regional.row(z,y,0,x1-x0)
                    control=naive.row(z,y,0,x1-x0)
                    count+=sum(a!=b for a,b in zip(reference,candidate))
                    naive_count+=sum(a!=b for a,b in zip(reference,control))
                    checked+=len(reference)
            if count:raise ValueError('Regional prediction differs from reference')
            if naive_count!=case['naive_differing_values']:raise ValueError('Naive control counts differ')
            rows.append({'case':case['index'],'regional_differences':count,'naive_differences':naive_count})
    return {'status':'passed','verified_files':len(names),'cases':len(cases),'compared_values':checked,'results':rows,
        'scope':'Saved-file integrity and exact output equivalence. No model was run; speed and ink accuracy are not verified by this command.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--json',action='store_true')
    args=p.parse_args();result=verify(args.package)
    if args.json:print(json.dumps(result,indent=2))
    else:
        print(f"PASS: {result['verified_files']} file hashes; {result['cases']} cases; {result['compared_values']:,} saved values match exactly.")
        print(result['scope'])


if __name__=='__main__':main()
