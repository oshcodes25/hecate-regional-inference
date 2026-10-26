import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify import U8Array,safe_path,verify,digest


def save_u8(path,shape,data,version=1,fortran=False):
    header=repr({'descr':'|u1','fortran_order':fortran,'shape':shape}).encode()+b'\n'
    prefix=b'\x93NUMPY'+bytes([version,0])+struct.pack('<H' if version==1 else '<I',len(header))
    path.write_bytes(prefix+header+bytes(data))


class StandardVerifierTests(unittest.TestCase):
    def test_row_offsets_and_versions(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'a.npy'
            for version in (1,2,3):
                save_u8(p,(2,3,4),range(24),version)
                with U8Array(p) as a:self.assertEqual(a.row(1,2,1,4),bytes([21,22,23]))

    def test_rejects_bad_layout_and_trailing_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'a.npy';save_u8(p,(2,2),[1,2,3,4],fortran=True)
            with self.assertRaises(ValueError):U8Array(p)
            save_u8(p,(2,2),[1,2,3,4,5])
            with self.assertRaises(ValueError):U8Array(p)

    def test_path_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);(p/'nested').mkdir();(p/'external.txt').write_text('private')
            with self.assertRaises(ValueError):safe_path(p/'nested','../external.txt')

    def test_equivalence_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);save_u8(p/'full.npy',(3,4),range(12));save_u8(p/'roi.npy',(2,2),[5,6,9,10]);save_u8(p/'naive.npy',(2,2),[0,6,9,0])
            case={'index':0,'roi_xyxy':[1,1,3,3],'outputs':{k:k+'.npy' for k in ('full','roi','naive')},'naive_differing_values':2}
            (p/'cases.json').write_text(json.dumps([case]));files=[{'path':x.name,'sha256':digest(x),'bytes':x.stat().st_size} for x in p.iterdir()]
            (p/'MANIFEST.json').write_text(json.dumps({'files':files}));self.assertEqual(verify(p)['compared_values'],4)
            (p/'roi.npy').write_bytes((p/'roi.npy').read_bytes()[:-1]+b'\x00')
            with self.assertRaises(ValueError):verify(p)
