import contextlib
import io
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from hecate_roi import schedule,axis_starts,predict_roi,load_runtime
try:
    import torch
except ImportError:
    torch=None


class ScheduleTests(unittest.TestCase):
    def test_partial_end_tile_is_included(self):
        self.assertEqual(axis_starts(19,8,4),[0,4,8,11])
        self.assertEqual(axis_starts(3,8,4),[0])

    def test_roi_uses_original_batch_groups(self):
        p=schedule((6,17,19),(6,8,8),(8,8,10,10),4,3)
        full=[(y,x) for y in [0,4,8,9] for x in [0,4,8,11]]
        for group in p['groups']:
            start=group['global_start'];self.assertEqual(group['origins'],full[start:start+3])
        self.assertGreater(p['scheduled_tiles'],p['contributing_tiles'])

    def test_bounds_and_coverage_exhaustively(self):
        for size in range(1,22):
            for stride in (1,3,4,8):
                for batch in (1,3):
                    for x in range(size):
                        p=schedule((6,size,size),(6,8,8),(x,0,x+1,size),stride,batch)
                        self.assertTrue(p['groups']);self.assertLessEqual(p['scheduled_tiles'],p['full_tiles'])
                        coverage=np.zeros((size,1),int)
                        for group in p['groups']:
                            for y,xx in group['origins']:
                                if xx<=x<xx+8:coverage[y:min(y+8,size)]+=1
                        self.assertTrue((coverage>0).all())

    def test_invalid_roi(self):
        for roi in ((0,0,0,1),(-1,0,1,1),(0,0,17,3),(0,0,1.5,1),(False,0,1,1)):
            with self.assertRaises(ValueError):schedule((6,16,16),(6,8,8),roi)

    def test_known_tile_saving(self):
        p=schedule((64,512,512),(64,256,256),(144,144,208,208))
        self.assertEqual((p['scheduled_tiles'],p['full_tiles']),(4,9))
        self.assertEqual(p['temporary_2d_bytes'],32768)


@unittest.skipIf(torch is None,'Torch is optional in the main research environment')
class RuntimeEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        path=Path(__file__).resolve().parents[1]/'data/paired-resolution-audit/hecate-runtime-pinned.py'
        cls.runtime=load_runtime(path)
        class Model(torch.nn.Module):
            def __init__(self):
                super().__init__();self.anchor=torch.nn.Parameter(torch.zeros(()));self.patch_size=(6,8,8)
                self.divisor=200.;self.margin=1
            def forward(self,image,valid=None):
                # Explicit whole-patch and batch dependence detects lost context,
                # regrouped active patches, and changed last-batch size.
                return image.mean(2)*6-image.mean()*4+self.anchor
            def forward_3d(self,image):
                return image*6-image.mean()*4+self.anchor
        cls.model=Model().eval()

    def compare(self,shape,roi,batch=1,reverse=False,three_d=False,blank=False,stride=4):
        volume=np.random.default_rng(7).integers(1,255,shape,dtype=np.uint8)
        volume[:,:3,:3]=0
        if blank:volume[:]=0
        x0,y0,x1,y1=roi
        out_shape=shape if three_d else shape[-2:]
        ref=np.zeros(out_shape,np.uint8)
        with torch.inference_mode(),contextlib.redirect_stdout(io.StringIO()):
            self.runtime.predict(self.model,volume,ref,reverse,stride,batch,'fp32',three_d=three_d)
        output=np.full(((shape[0],) if three_d else ())+(y1-y0,x1-x0),255,np.uint8)
        class Lazy:
            def __init__(self):self.shape=volume.shape;self.dtype=volume.dtype;self.reads=[]
            def __array__(self,*args,**kwargs):raise AssertionError('Full source materialized')
            def __getitem__(self,key):self.reads.append(key);return volume[key]
        lazy=Lazy();report=predict_roi(self.model,lazy,output,roi,reverse,stride,batch,'fp32',three_d)
        np.testing.assert_array_equal(output,ref[...,y0:y1,x0:x1])
        self.assertEqual(len(lazy.reads),report['scheduled_tiles'])
        if blank:self.assertEqual(report['neural_tiles'],0)

    def test_context_batch_direction_depth_matrix(self):
        for batch in (1,3,7):
            for reverse in (False,True):
                for three_d in (False,True):
                    with self.subTest(batch=batch,reverse=reverse,three_d=three_d):
                        self.compare((9,17,19),(5,6,15,16),batch,reverse,three_d)

    def test_small_padding_and_full_region(self):
        for three_d in (False,True):
            self.compare((7,3,5),(0,0,5,3),3,True,three_d)
            self.compare((8,17,19),(0,0,19,17),3,False,three_d)

    def test_blank_and_edge_regions(self):
        self.compare((9,17,19),(17,15,19,17),3,True,True)
        self.compare((9,17,19),(0,0,1,1),3,False,False)
        self.compare((9,17,19),(5,6,15,16),3,True,True,True)

    def test_custom_stride(self):
        for stride in (1,3,8):self.compare((8,17,19),(7,6,16,15),3,False,False,stride=stride)

    def test_training_model_rejected(self):
        self.model.train()
        try:
            with self.assertRaises(ValueError):predict_roi(self.model,np.zeros((6,8,8),np.uint8),np.zeros((1,1),np.uint8),(0,0,1,1))
        finally:self.model.eval()
