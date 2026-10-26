# Context-preserving regional inference for Hecate

**Author:** Oisin McGlone · oisinmcglone25@gmail.com  
**Category:** Progress Prize — reading software, reproducible inference  
**Status:** Private reviewer edition v2; no submission or publication made. Repeated performance validation against careful context cropping remains pending.

Hecate users inspecting a small section can change the model's prediction simply by cropping its input: tile origins, surrounding context and overlap weights change. Running the entire parent field preserves the reference result but spends work outside the area being inspected.

This contribution adds a regional API and CLI to the pinned standalone Hecate runtime. It keeps the original full-array tile grid, final edge tiles, original batch groups, complete CT contexts, depth direction, support and Hann blending. It evaluates only the batch groups that contribute to the requested region and allocates temporary accumulators for that region alone.

Across eight registered tests on real CT from PHerc9B and PHerc500P2, at 2.4/9.6 µm and with 2D/3D outputs, all **541,184 regional saved values** equal the corresponding unmodified full-field outputs. The two primary 2.4 µm 2D cases require **4 instead of 9 neural tiles**, have **2.24× geometric-mean measured CPU speedup**, and use **54.4×–64.0× smaller temporary accumulators**. Naïve input cropping changes **96.29%–99.95%** of their saved values. Synthetic tests additionally cover blank inputs, small padded fields, custom strides, boundaries, reverse depth and batch grouping.

The submission includes a short visual walkthrough, a standard-library-only saved-output verifier, a clean-installation record, an offline interactive CT/output viewer, the implementation and tests, real bounded input crops, all saved outputs, a frozen experiment plan, measurements, checksums and a portable reproduction command. No model fitting or paid compute was used. The integration accepts the existing Hecate model and array interface and writes PNG/NPY with coordinate metadata.

The established global-grid technique in villa PR #1247 is the closest predecessor and is credited. Hecate's existing 2D optimization and paired-feature proposal are also credited; neither is claimed as our work. The concrete contribution is the separate Hecate implementation and verification, including original batch grouping and 3D depth handling.

This is a correctness/efficiency submission. The full-field output is a software reference, not ground-truth ink. The fields are previously exposed research inputs; no untouched-reading validation or new letters are claimed. CPU float32 is validated; there is no GPU or cloud-I/O performance claim. Timing uses one balanced-order run per case and should be independently reproduced on target hardware.

The code is supplied under MIT with upstream attribution. Included CT data and derived scan visualizations retain their original CC BY-NC terms. We can provide the package privately for review; public release has not occurred. The [current Progress Prize rules](https://scrollprize.org/prizes#progress-prizes) allow private submission and require permissive open-source release to accept an award. The next published deadline is **31 October 2026, 23:59 Pacific**; the owner's intended review date is 30 October.

Files to review first: `START_HERE.html`, `REPORT.html`, `README.md`, `src/hecate_roi.py`, and `evidence/result.json`. Run `python3 verify.py` to verify the supplied artifact independently without downloading weights.

## Stronger comparison being prepared

A carefully selected crop retaining the original aligned context is an important alternative to our regional API. It may match the reduced model workload, while allocating larger temporary blending arrays. We explicitly do not claim a speed advantage over that alternative without measurements. The next registered study fixes three balanced-order repeats across two fine-resolution centre cases and edge/centre/large requests in three coarse-resolution specimens. It is waiting for AC power; no result from that study is included in the current claim.

The fresh environment installed all 11 pinned dependency packages from recorded binary wheels, passed `pip check`, all ten original portable tests and the 541,184-value saved-output verification. This establishes a clean installation on the same laptop. It does not establish independent hardware replication or a fresh neural-model rerun.
