import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_repeats import check_case


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class RepeatedEvidenceTests(unittest.TestCase):
    def fixture(self,root):
        for name in ['src/hecate_roi.py','data/paired-resolution-audit/hecate-runtime-pinned.py']:
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture, not executed')
        np.save(root/'input.npy',np.zeros((64,256,256),np.uint8),allow_pickle=False)
        case={'index':0,'sample':'fixture','sampling':9.6,'reverse':False,'input':'input.npy','checkpoint_sha256':'0'*64,'result':'result.json'}
        full=(np.arange(4096,dtype=np.uint16)%251).astype(np.uint8).reshape(64,64)
        boxes={'edge':[0,0,16,16],'centre':[36,36,52,52],'large':[16,16,48,48]};rows=[]
        for repeat in range(3):
            for method,name in [('full',None)]+[(m,n) for m in ['regional','halo'] for n in boxes]:
                box=boxes.get(name);image=full if method=='full' else full[box[1]:box[3],box[0]:box[2]]
                file=root/f'{repeat}-{method}-{name}.npy';np.save(file,image,allow_pickle=False)
                row={'repeat':repeat,'method':method,'region':name,'roi_xyxy':box,'context_xyxy':[0,0,64,64] if method=='halo' else None,
                     'seconds':{'full':10.,'regional':3.,'halo':3.2}[method],'neural_tiles':1,
                     'temporary_accumulator_bytes':8*(image.size if method=='regional' else 4096),'output':file.name,'output_sha256':digest(file)}
                if method!='full':row['different_values']=0
                rows.append(row)
        result={'status':'completed','sample':'fixture','sampling_um':9.6,'reverse':False,'input_shape':[16,64,64],
                'input_sha256':digest(root/'input.npy'),'checkpoint_sha256':'0'*64,'reader_sha256':digest(root/'src/hecate_roi.py'),
                'runtime_sha256':digest(root/'data/paired-resolution-audit/hecate-runtime-pinned.py'),'rows':rows}
        (root/'result.json').write_text(json.dumps(result));return case,result

    def test_all_values_and_recorded_statistics(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);case,result=self.fixture(root);counts,rows=check_case(root,case)
            self.assertEqual(counts,{'regional_values':4608,'halo_values':4608,'repeated_full_values':8192})
            self.assertEqual(len(rows),3);self.assertEqual(rows[0]['statistics']['full_over_regional']['median'],10/3)

    def test_changed_prediction_even_with_updated_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);case,result=self.fixture(root);row=next(x for x in result['rows'] if x['method']=='regional')
            file=root/row['output'];array=np.load(file,allow_pickle=False);array[0,0]^=1;np.save(file,array,allow_pickle=False)
            row['output_sha256']=digest(file);(root/'result.json').write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError,'Saved prediction differs'):check_case(root,case)

    def test_omitted_trial_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);case,result=self.fixture(root);result['rows'].pop();(root/'result.json').write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError,'Missing or unexpected'):check_case(root,case)
