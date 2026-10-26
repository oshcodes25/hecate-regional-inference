# Repeated comparison and reviewer edition v3 — QA

All five fixed worker cases completed all three repetitions. Four registered gates passed. The power-interrupted second-case attempt saved no predictions; the failure and a reviewed operational continuation are preserved. Case 0 was reused byte-for-byte. The original 2400-second aggregate cap includes the interruption; actual worker time was 1205.650 seconds. Peak worker RSS was 6,688,260,096 bytes, below 8 GiB. Saved prediction files total 1,818,564 bytes.

- Eleven requests × three repeats, with full-field, regional and careful context-crop methods. Eighty-one prediction arrays retained; no completed trial removed. Completed measured runs used 435 neural tiles, excluding warmups and the interrupted attempt.
- All 106,668 new saved regional values and 106,668 context-crop values agree with their corresponding full-field references. Full-field repeats agree across another 1,063,240 value comparisons. These counts include repeated measurements of the same regions, not independent ink examples.
- The three comparable earlier E079 cases reproduce exactly in all three fresh-environment repeats. No new ink truth or independent hardware replication is established.
- The standard-library verifier checks package hashes, all original saved results, the new outputs, shapes, provenance and independently recomputed timing/storage summaries and gates.
- Main suite: 270 tests, 44 expected Torch skips; all executed tests passed. Portable package suite: 17 tests passed. New tests deliberately alter a prediction while updating its hash and omit a trial; both invalid cases are rejected.
- An initial direct-helper test exposed macOS /var versus /private/var path normalization. Resolving the root at helper entry fixed it; initial test logs are retained. The actual package verifier already normalized its root and passed before this correction. No model code, prediction or experimental setting changed.
- All 767,228 values embedded in the new viewer match the underlying arrays, including raw CT data. Predictions are not generated illustrations. The original CT preparation and licenses remain documented.
- Offline browser checks: 11 requests × two brightness settings × two difference settings = 44 states. Every prediction-canvas pixel was checked; the scientific figure decoded, with no JavaScript exceptions or page overflow at desktop 1440 px and mobile 390 px. Five screenshots and the scientific figure were inspected.
- HTML and scientific PNG regenerate byte-for-byte using rebuild_view.py in the recorded plotting environment. No model inference is involved in that check.

The larger requests provide no compute reduction and can be slightly slower than the full field. For small requests, careful cropping has the same neural tile count and similar time. The measured extra benefit is automatic context handling and 16–36× smaller temporary accumulators; total model RAM reduction and superiority over all existing tools are not claimed. The unusually slow first fine full-field trial remains included in the observed timing range.

The final ZIP inventory, CRC and verification after extraction outside the workspace are recorded in the workspace completion record. All software remains private. No model or browser job is left running after QA.
