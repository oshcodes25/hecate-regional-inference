# Reviewer edition, version 2

Start with **START_HERE.html**. It uses real saved CT/output arrays to explain the contribution in three steps. Run **python3 verify.py** for the saved-output check without installing any packages. The original E079 scientific viewer, numerical results, source implementation and predictions are preserved.

**New in this edition:** a plain-language walkthrough, a standard-library verifier with tamper-detection tests, a clean virtual-environment installation with all 11 dependency versions and wheel hashes recorded, and a preregistered stronger benchmark. See `CHANGES.md` and `QA-REVIEW.md` for the new work. The inherited `QA.md` describes the original package, not additional checks of this edition.

**Important remaining comparison:** a carefully aligned surrounding-context crop may match our reduction in neural work. This was not measured in E079. The separately registered three-repeat study is **waiting for AC power and has not executed**. Its plan and portable worker are included under `repeatability/`. Do not read the older one-trial timings as evidence of superiority over this stronger alternative.

# Hecate regional inference

Request a small output region without changing its full-field scan context. The API keeps Hecate's original tile grid, complete batch groups, edge tiles and blending weights, then limits its accumulators to the requested region.

**Measured result:** all 541,184 saved regional values matched the original full-field result across eight real-CT cases. The two primary 2.4 µm, 2D cases used 4 neural tiles instead of 9 (55.6% fewer), with a geometric-mean CPU speedup of **2.24×**. This is an implementation-equivalence result, not ground-truth ink accuracy or new text.

## View the result

Open **`START_HERE.html`** for the short visual walkthrough, then `REPORT.html` for the complete eight-case scientific viewer. It works offline and includes the actual CT, original prediction, naïve crop, corrected output, depth controls and all case results. Keep `comparison.png` and `context.png` beside it.

## Verify without running a model

Python 3.10+ is sufficient; no third-party package is needed:

```sh
python3 verify.py
```

This checks every packaged file hash and compares all saved regional values with the corresponding full-field output. It also independently recounts the naïve-crop differences. No model weights or network access are required.

## Use the software

The tested environment is Python 3.12.15, NumPy 2.2.6 and PyTorch 2.8.0 on a Mac M2 Pro, CPU float32, four threads. For the exact freshly installed Python 3.12 environment, use `python -m pip install -r requirements-review.lock` in a separate virtual environment. `requirements.txt` retains the minimal direct dependencies. The fresh installation was verified on this same Mac, not a second computer. The pinned upstream runtime is included with its MIT license; model checkpoints are not included.

Download the desired checkpoint from [Hecate at the tested revision](https://huggingface.co/scrollprize/hecate/tree/9cb86e500e944b11a06a7020403cde5dffb5bcb2) into `models/`. Each file is about 523 MB. Exact hashes are in `cases.json`.

```sh
python -m pip install -r requirements.txt
python src/hecate_roi.py \
  --runtime data/paired-resolution-audit/hecate-runtime-pinned.py \
  --input inputs/PHerc0009B.npy --spacing-um 2.4 \
  --roi 144 144 208 208 --dry-run

python src/hecate_roi.py \
  --runtime data/paired-resolution-audit/hecate-runtime-pinned.py \
  --checkpoint models/hecate_2.4um.pth \
  --input inputs/PHerc0009B.npy --spacing-um 2.4 \
  --roi 144 144 208 208 --output my-region.png
```

ROI coordinates are half-open `X0 Y0 X1 Y1` in the **supplied full input array**. Provide the original source array or lazy Zarr store, not a file already cropped to the ROI. Use matching spacing; this command does not resample. Local NPY inputs need no additional packages. Zarr inputs need the upstream optional dependencies `zarr>=2.18,<4` and `numcodecs>=0.12,<1`. The output can be PNG or NPY; `--output-3d my-region-3d.npy` saves depth-aligned uint8 values and a JSON provenance sidecar. Requesting both outputs retains upstream's two inference passes. Existing outputs are never overwritten.

Python integration:

```python
from hecate_roi import predict_roi
# model: loaded, evaluated Hecate; volume: complete uint8 ZYX array/store
# output: uint8 (roi_height, roi_width), or (source_depth, roi_height, roi_width)
metadata = predict_roi(model, volume, output, (144, 144, 208, 208))
```

Keep the same checkpoint, stride, batch size, precision and device as the full run. This release verifies CPU float32; CUDA/bfloat16 equivalence is not claimed. Complete original batch groups can include tiles outside the ROI; keeping them preserves numerical context. The reported dry-run counts include blank tiles, which may skip neural inference.

## Rerun a benchmark case

```sh
python reproduce.py --rerun --case 0 --models models --output rerun-case-0
python -m unittest discover -s tests -v
```

Cases 0–7 are listed in `cases.json`. Each model rerun also checks the supplied package before inference. Local timings will vary. The benchmark excludes model loading, includes a fixed warmup, and balances full/ROI execution order across specimens. There is one measured run per case; no population-level timing confidence interval is claimed.

| Specimen | µm | Output | Depth order | Corrected differences | Naïve differences | Mean score error | Local speedup |
|---|---:|---|---|---:|---:|---:|---:|
| PHerc0009B | 2.4 | 2D | forward | 0 | 96.29% | 0.1417 | 2.30× |
| PHerc0500P2 | 2.4 | 2D | forward | 0 | 99.95% | 0.0980 | 2.18× |
| PHerc0009B | 2.4 | 3D | reverse | 0 | 22.53% | 0.0011 | 2.25× |
| PHerc0500P2 | 2.4 | 3D | forward | 0 | 38.42% | 0.0143 | 2.44× |
| PHerc0009B | 9.6 | 2D | forward | 0 | 94.14% | 0.1125 | 2.19× |
| PHerc0500P2 | 9.6 | 2D | reverse | 0 | 100.00% | 0.0275 | 1.40× |
| PHerc0009B | 9.6 | 3D | reverse | 0 | 43.90% | 0.0073 | 2.21× |
| PHerc0500P2 | 9.6 | 3D | reverse | 0 | 65.48% | 0.0108 | 1.50× |

## What is and is not established

The implementation preserves the tested original output while using fewer tiles and smaller temporary blend files. The reference is the **entire supplied parent field**, not a whole scroll or verified physical ink. Parent fields are 512×512 and 472×472 pixels at 2.4 µm; the coarse software tests use fixed 4×4×4 block averaging. These two physical fields were previously exposed in our research. No labels, threshold optimization or reserved reading-test regions were used. There is no claim of better ink recall, newly legible letters, benchmark training exclusion or GPU speedup.

The global-grid principle predates this work: [villa PR #1247](https://github.com/ScrollPrize/villa/pull/1247) fixes it for surface segmentation. [ArcheyChen's Hecate fast path](https://github.com/ArcheyChen/vesuvius-eligible-scouting/blob/c73d0dd5c0bf1913fd1a6551f6dcae428ce0cc56/docs/hecate_perf.md) is an existing 2D speed improvement. [Hecate discussion #1](https://huggingface.co/scrollprize/hecate/discussions/1) already proposes shared 2D/3D features. Our contribution is this Hecate regional implementation, its batch/edge/depth equivalence checks and measured savings; no field-wide novelty claim is made.

The experimental source is frozen in `evidence/registered-hecate-roi.py`. The packaged CLI adds an early ROI validation check before output allocation. All scheduling/inference/loading functions are AST-identical; `evidence/packaging-change.json` records the difference. The original registered plan and results are retained unchanged with their original workspace-relative provenance paths. `cases.json` supplies portable paths.

## Attribution and status

Author: Oisin McGlone. This is a private submission package; it has not been submitted, posted or published. `SUBMISSION.md` is the review-ready entry text. Prize suitability and an award remain decisions for the organizers.

Software: MIT, with Vesuvius Challenge upstream attribution. Data/derived scan visualizations retain their source terms (CC BY-NC 4.0 unless specified otherwise); they are not relicensed under the code license. Dataset citation: Angelotti et al., *Vesuvius Challenge — CT Scans of Herculaneum Papyri*. See [official data information](https://scrollprize.org/data), `DATA-NOTICE.md`, and the included source/provenance records.

Local Zarr v2 loading and packaged CLI planning were also checked: 16,777,216 source voxels and the NPY/Zarr schedules matched exactly. This is an input-format check without model execution; see QA-REVIEW.md.
