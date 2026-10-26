# Hecate regional reader — repeated comparison, v3

Open **START_HERE.html**. The completed comparison includes 11 requests across three existing CT fields, with three balanced-order repeats. Both regional inference and carefully aligned context cropping are compared with the original full-field prediction. All four registered gates passed.

The five central requests have median full/regional time ratios of **2.20–2.43×**. Small-request regional/context-crop time ratios are **0.965–1.018** (below 1 means regional was quicker). Both small-region methods evaluate the same contributing tiles. Do not claim a novel neural-work reduction or clear speed superiority over careful cropping. The additional contribution is automatic original-grid handling, the existing batch/3D API, and smaller temporary output accumulators. For the tested small requests these arrays are 16–36× smaller than in the context-crop alternative. These are disk-backed blending arrays, not total model RAM.

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

Timing variability is retained: the PHerc9B fine full-field runs took 61.850–121.213 seconds (median 65.699). No completed trial was discarded. Three local repeats and a single hardware setup do not establish general runtime bounds.
