# Reviewer guide

## Fastest verification path

From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python.exe -m backend.scripts.prepare_embedding_model
npm.cmd --prefix frontend install

.\.venv\Scripts\python.exe -m backend.scripts.evaluate_pipeline --runs 3 --mode template
.\.venv\Scripts\python.exe -m backend.scripts.generate_final_submission
.\.venv\Scripts\python.exe -m backend.scripts.report_run_usage
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_final_submission_supplied_data.py -q
```

Inspect:

- [`final_submission.csv`](../backend/data/output/final_submission.csv)
- [`evaluation_report.md`](../backend/data/output/evaluation/evaluation_report.md)
- [`reproducibility_manifest.json`](../backend/data/output/evaluation/reproducibility_manifest.json)
- [`run_usage_report.json`](../backend/data/output/run_usage_report.json)

Optional UI startup uses two terminals:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.run_api
npm.cmd --prefix frontend run dev
```

Open `http://127.0.0.1:5173`, run the analysis once to publish an API snapshot,
then investigate the queue. These addresses are local only.

## Two-minute repository review

1. Read the root [`README`](../README.md) and [traceability table](CASE_STUDY_TRACEABILITY.md).
2. Inspect the pipeline entry point in [`pipeline.py`](../backend/app/application/pipeline.py).
3. Inspect weighted analytics in [`weekly_cost.py`](../backend/app/services/analytics/weekly_cost.py) and baselines in [`baselines.py`](../backend/app/services/analytics/baselines.py).
4. Inspect deterministic evidence checks in [`gate.py`](../backend/app/services/evidence/gate.py).
5. Inspect output ownership in [`final_submission.py`](../backend/app/services/reporting/final_submission.py).
6. Review unit/integration fixtures under [`backend/tests`](../backend/tests/) and current machine evidence above.

## Concise ten-minute product path

1. State the problem and deterministic/model authority boundary.
2. Show the verified 2,940 / 7 / 728 / 19 counts.
3. Select one anomaly from the investigation queue.
4. Open Cost Courtroom and show the weighted cost and both baselines.
5. Compare an accepted note with a rejected gate result.
6. Show an Operational Lead and its explicit non-causal caveat.
7. Ask one grounded assistant question if time permits.
8. Open evaluation metrics and the three-run hashes.
9. Export the exact eight-column CSV.
10. Close with the principal trade-offs and production evolution.

This is intentionally a feature order, not a memorized presentation script. Detailed
timing, screenshots, and emergency-demo recovery belong to later packaging work.
