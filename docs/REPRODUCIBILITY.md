# Reproducibility

## Procedure

The required check runs three fresh subprocesses against unchanged inputs:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.evaluate_pipeline --runs 3 --mode template
```

Each run has an isolated output directory. The harness sets `PYTHONHASHSEED=0`,
`TZ=UTC`, template explanation mode, local-only embeddings, UTF-8 output, and the
pinned embedding revision. Template generation has no sampling temperature or
hosted model call. Rows are deterministically sorted before serialization.

## Inputs and configuration

| Input | SHA-256 |
|---|---|
| `shipment_records.csv` | `1a2b4d66c4dc694111ba37b966486b5b0650df9ec8687402f3434117b140f4b6` |
| `context_notes.csv` | `875c57a896ac3dfac0f712f8865b287bb5d2bd5423d26e798297b74dce87e6dc` |
| `sample_output_format_v2.csv` | `1ea902faca37bef6816e0878dc17bdb509a88f9ff9d4f101373e3af03994201f` |

Configuration fingerprint:
`ebea8117a90d5c2b67180e6130303f614b5723cf95ad1294077a8031e96c4706`.
The recorded environment is Microsoft Windows 10.0.26200/AMD64 with CPython
3.12.6 and local
`sentence-transformers/all-MiniLM-L6-v2` revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.

## Result

| Run | Canonical CSV SHA-256 | Candidate/verdict fingerprint | Result |
|---|---|---|---|
| `run_01` | `73fad5f7244fe4e016dee055b96da98d90107da93fdd46d09b092a1975d678f7` | `62a7db940c895dc306d56848c65a950990f88e200a641d4f00178879e3722dea` | Identical |
| `run_02` | `73fad5f7244fe4e016dee055b96da98d90107da93fdd46d09b092a1975d678f7` | `62a7db940c895dc306d56848c65a950990f88e200a641d4f00178879e3722dea` | Identical |
| `run_03` | `73fad5f7244fe4e016dee055b96da98d90107da93fdd46d09b092a1975d678f7` | `62a7db940c895dc306d56848c65a950990f88e200a641d4f00178879e3722dea` | Identical |

The candidate/verdict fingerprint is the full explanation audit hash; it includes
route, week, verdict, selected/supporting note IDs, citation IDs, source, usage, and
reason hash. The operational root-cause artifact was also byte-identical at
`dd584659bea3e9bac3455eecd946f4f3911ae57a49a829711ced064ab6149968`.
The machine-readable evidence is in
[`reproducibility_manifest.json`](../backend/data/output/evaluation/reproducibility_manifest.json).

## Live-mode boundary

Live wording may vary and is not accepted as formal reproducibility evidence. If a
live mode is evaluated separately, canonical numbers, candidate flags, verdicts,
and note IDs must still be identical; only validated wording may vary.
