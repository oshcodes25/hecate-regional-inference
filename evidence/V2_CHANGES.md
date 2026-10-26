# Changes from the original E079 package

- Added START_HERE.html: actual CT and saved predictions, three explanatory steps, both primary specimens, linked display brightness, precise scope and practical uses.
- Added verify.py: Python standard library only, file hashes, strict uint8 NPY parsing, all 541,184 saved values and the naïve control counts. Four targeted tests include a deliberately altered output and an escaping path.
- Installed 11 exact dependency versions into a newly created Python 3.12.15 virtual environment. Wheel hashes, install/dependency logs and ten passing portable tests are retained. This was performed on the same Mac M2 Pro.
- Registered a repeated comparison against full-field inference and independently selected surrounding-context crops before running it. All cases, comparisons, gates, failure policy and resource limits are recorded. It is waiting for power, with zero model attempts.
- Included the third already available CT input needed by the new benchmark, its standalone measurement worker and commands. No new scans were downloaded.

The E079 model, inference implementation, eight-case settings, labels, arrays, measurements, detailed report and predecessor credits are unchanged. The new package is a separate directory; the original package and archive remain frozen.

This edition does not claim additional performance measurements, improved ink accuracy, GPU validation, community adoption or a second-machine replication.

Local Zarr v2 loading and packaged CLI planning were also checked: 16,777,216 source voxels and the NPY/Zarr schedules matched exactly. This is an input-format check without model execution; see QA-REVIEW.md.
