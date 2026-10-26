# Context-preserving regional inference for Hecate

Author: Oisin McGlone · oisinmcglone25@gmail.com  
Category: Progress Prize, reading software  
Status: Private draft; no submission or publication made.

Researchers inspecting a small region can change Hecate's output by cropping its input without preserving the original context and tile grid. This regional API accepts the original array and desired output coordinates, preserves the original contributing tile/batch contexts and blending, and limits temporary accumulation to the requested output.

The original eight-case experiment matched all 541,184 saved regional values across two fields, fine/coarse resolutions, 2D/3D outputs and batch/depth configurations. A separate preregistered follow-up now compares full-field, regional and carefully aligned context-crop inference for 11 fixed requests on three existing fields, with three balanced-order repeats in a fresh pinned environment. All four registered gates passed. Every trial and saved output is supplied.

For the five central requests, median full/regional time ratios are 2.20–2.43×. The important competing context-crop method also reduces the neural tile count. We therefore claim no invention of that principle or clear speed superiority over careful cropping. The additional contribution is a reusable Hecate regional interface, preservation of original batch/depth behavior, smaller temporary output accumulators and a reproducible comparison. Small requests use 16–36× less temporary accumulation than the aligned-crop baseline; total model-memory reduction is not claimed. Large requests are included and may need all tiles.

The package includes an offline interactive explanation, real bounded CT inputs, all measured outputs, fixed plans, source/runtime revisions, checkpoint hashes, tests and a standard-library-only saved-result verifier. `python3 verify_repeats.py` checks the evidence; the separate portable worker commands perform fresh inference. Local Zarr v2 input loading and CLI scheduling have also been checked. No paid compute or training was used.

The global-grid principle in villa PR #1247 is the closest credited predecessor; existing Hecate fast-path and paired-feature work is also credited. This is correctness/efficiency software, not new verified writing. The reference is software output on small supplied fields, not ink ground truth. The fields were previously exposed; fresh reading validation, independent hardware, GPU/cloud performance and community adoption are not established.

Review START_HERE.html, README.md, src/hecate_roi.py, repeatability/result.json and the included plans. Code is MIT with upstream attribution; data and derived views retain their source terms. The current Progress Prize rules allow private submission and require permissive public release to accept an award. The published next deadline is 31 October 2026 at 23:59 Pacific; acceptance and award size are for the organizers to decide.

Timing variability is retained: the PHerc9B fine full-field runs took 61.850–121.213 seconds (median 65.699). No completed trial was discarded. Three local repeats and a single hardware setup do not establish general runtime bounds.

A power interruption stopped the initial second-case attempt before it saved predictions. Its log and consumed time are preserved; a reviewed operational amendment reused the completed first case and executed the remaining cases unchanged within the original aggregate resource cap.
