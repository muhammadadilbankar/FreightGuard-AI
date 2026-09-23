# Input data integrity record

The challenge files were supplied directly in `backend/data/input/` on
2026-09-22. The repository does not clean or rewrite them in place. The initial
measurement made before final verification was:

| File | Bytes | SHA-256 |
|---|---:|---|
| `shipment_records.csv` | 259523 | `1a2b4d66c4dc694111ba37b966486b5b0650df9ec8687402f3434117b140f4b6` |
| `context_notes.csv` | 1715 | `875c57a896ac3dfac0f712f8865b287bb5d2bd5423d26e798297b74dce87e6dc` |
| `sample_output_format_v2.csv` | 903 | `1ea902faca37bef6816e0878dc17bdb509a88f9ff9d4f101373e3af03994201f` |

Because the files arrived at their canonical destination, no copy operation was
necessary. A second measurement after tests, linting, and API verification matched
these byte sizes and hashes exactly.
