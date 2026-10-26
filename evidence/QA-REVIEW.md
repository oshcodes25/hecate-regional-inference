# Reviewer edition v2 — verification record

The original E079 measurements and private archive remain unchanged. This edition adds presentation, verification and preparation for a stronger comparison. It does not add new model inference or ink findings.

- Main workspace suite: 267 tests, 44 expected Torch skips; all executed tests passed.
- Original portable suite in a newly created, pinned Python 3.12 environment: 10 tests passed; dependency consistency check passed. All 11 installed packages and downloaded wheel hashes are recorded.
- This edition's portable suite: 14 tests passed, including strict NPY parsing, tamper detection and path containment. Its saved-output check compares all 541,184 values and independently recounts the naïve control differences. The verifier was exercised with Python isolated mode and site-packages disabled (`python3 -I -S`).
- Offline browser check: desktop 1440 px and mobile 390 px, no horizontal overflow or JavaScript exceptions. Both specimens, all three explanation steps and two brightness settings passed 12 state checks. Every pixel in each of the three 64×64 prediction panels was checked against the source arrays at each state. Five screenshots were inspected.
- Actual local Zarr v2 integration: all 16,777,216 source voxels survived the local store round trip exactly; the packaged CLI produced identical NPY and Zarr schedules (four selected windows). This checked loading and dry-run planning only. No checkpoint was loaded. It is not a Zarr v3, cloud performance or neural inference result.
- The new walkthrough is generated from the original saved arrays. CT outside the selected context is visually shaded; raw inputs are preserved. The scientific REPORT.html and both scientific figures retain their original bytes.

The repeated performance study has zero attempts and is waiting for AC power. Its registered plan compares full-field inference, the regional implementation and independently selected aligned context cropping. A clean installation on the same laptop is not independent hardware replication. No Docker, CUDA, community-use, new-text or improved-ink-accuracy claim is made.

The final manifest covers the delivered files. The archive and extracted verification results are recorded separately in the workspace completion record to avoid a self-referential checksum. QA.md in this package remains the original E079 verification record.
