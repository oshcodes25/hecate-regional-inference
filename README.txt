HECATE REGIONAL INFERENCE

Open index.html to read the report and inspect the measurements.

The evidence/ directory contains the regional inference implementation,
bounded CT inputs, saved predictions, experiment settings and tests.

Verify the saved results from this directory:
  python3 -I -S evidence/verify_repeats.py --package evidence

Fresh inference:
Follow evidence/README.md and evidence/repeatability/README.md for the
pinned environment, checkpoint hashes and benchmark commands.
Checkpoints are downloaded separately from their recorded source.

Figure sources:
figure-provenance.json records the source data, scheduler output, display
transformations and image hashes. The CT overlays use the packaged scheduler;
the storage diagrams show the extents of the blending arrays.

Licences and attribution:
Code: evidence/LICENSE. Data and derived images: evidence/DATA-NOTICE.md.
