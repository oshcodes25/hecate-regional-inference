# Registered follow-up — not yet executed

The plan is frozen before measurement. `execution-at-packaging.json` records zero attempts, waiting for AC power. The original workspace launcher enforces AC power, an open lid, time and resource limits; it is not a background job.

The portable `measure.py` worker requires only Python, NumPy and Torch. It compares the original full-field runtime, our frozen regional API and independently selected aligned surrounding-context crops. It uses unchanged weights, four CPU threads, float32, batch size one, one excluded warmup, and three balanced-order repeats. All outputs and every time are saved; a differing or slow case must not be dropped. Large-region cases are sensitivity tests.

From the package directory, after installing `requirements-review.lock` and obtaining the checkpoints described in the main README, the first registered worker command is:

```sh
python -I repeatability/measure.py \
  --reader src/hecate_roi.py \
  --runtime data/paired-resolution-audit/hecate-runtime-pinned.py \
  --checkpoint models/hecate_2.4um.pth \
  --input inputs/PHerc0009B.npy --sample PHerc0009B \
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
