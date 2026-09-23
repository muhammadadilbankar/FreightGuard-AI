# Case-study traceability

This table maps each submission requirement to implemented code and current evidence.
The standalone original brief is not stored in this repository; this map uses the
requirements supplied for the exercise and the authoritative sample CSV schema.

| Brief requirement | Implementation | Verification | Artifact/result | Status |
|---|---|---|---|---|
| Directional route and supplied `route_type` grouping | [`normalization.py`](../backend/app/services/ingestion/normalization.py), [`weekly_cost.py`](../backend/app/services/analytics/weekly_cost.py) | `test_weekly_cost.py`, supplied-data integration tests | 7 directional routes | Implemented and verified |
| Monday-Sunday weeks with Monday `week_of` | [`weekly_cost.py`](../backend/app/services/analytics/weekly_cost.py) | `test_weekly_cost.py` | 728 route-week records | Implemented and verified |
| Weighted cost per tonne-km | [`weekly_cost.py`](../backend/app/services/analytics/weekly_cost.py) | `test_weekly_cost.py`, evaluation mathematics domain | Reconciles to shipment totals | Implemented and verified |
| Prior eight available observations | [`baselines.py`](../backend/app/services/analytics/baselines.py) | `test_baselines.py` | No look-ahead; audit counts retained | Implemented and verified |
| Fewer-than-eight behavior | [`baselines.py`](../backend/app/services/analytics/baselines.py) | early-history baseline tests | Uses every available prior observation | Implemented and verified |
| Same-week, same-type peer mean | [`baselines.py`](../backend/app/services/analytics/baselines.py) | peer-baseline tests | Route-level arithmetic mean | Implemented and verified |
| Current route excluded from peers | [`baselines.py`](../backend/app/services/analytics/baselines.py) | self-exclusion tests | Peer counts retained | Implemented and verified |
| Rising/out-of-ordinary detection | [`candidates.py`](../backend/app/services/analytics/candidates.py) | `test_candidate_detection.py` | 19 candidates at configured 20% threshold | Implemented and verified |
| Context-note retrieval | [`pipeline.py`](../backend/app/services/evidence/pipeline.py) | retrieval unit/integration tests | Sparse+dense reciprocal-rank fusion | Implemented and verified |
| Route/time/direction/cost/scope gates | [`gate.py`](../backend/app/services/evidence/gate.py) | evidence-rule and adversarial tests | Unsafe acceptance rate 0% | Implemented and verified |
| Exact note citation for justification | [`decisions.py`](../backend/app/services/evidence/decisions.py) | evidence and final-output tests | 3 justified rows cite selected notes | Implemented and verified |
| Unsupported evidence stays flagged | [`decisions.py`](../backend/app/services/evidence/decisions.py) | negative controls and evidence tests | 4 unexplained; 12 partial | Implemented and verified |
| Exact eight-column CSV | [`final_submission.py`](../backend/app/services/reporting/final_submission.py) | `test_final_submission_supplied_data.py` | [`final_submission.csv`](../backend/data/output/final_submission.csv) | Implemented and verified |
| Blank unmatched note ID | [`final_submission.py`](../backend/app/services/reporting/final_submission.py) | output-contract tests | Blank unless fully justified | Implemented and verified |
| Lightweight labeled evaluation | [`evaluation/`](../backend/app/evaluation/) and fixtures | Formal evaluation command | 109/109 checks PASS | Implemented and verified |
| Three untouched runs | [`reproducibility.py`](../backend/app/evaluation/reproducibility.py) | `evaluate_pipeline --runs 3` | [`reproducibility_manifest.json`](../backend/data/output/evaluation/reproducibility_manifest.json) | Implemented and verified |
| Randomness controls | evaluation subprocess environment and pinned model revision | reproducibility comparison | `PYTHONHASHSEED=0`, `TZ=UTC`, template mode | Implemented and verified |
| Full-run tokens, calls, and cost | [`report_run_usage.py`](../backend/scripts/report_run_usage.py) | focused usage-report test | [`run_usage_report.json`](../backend/data/output/run_usage_report.json) | Implemented and verified |
| Clean, navigable code | domain/service/application/API separation | Ruff, backend/frontend tests and builds | [Architecture](ARCHITECTURE.md) | Implemented and verified |
| Ten-minute walkthrough readiness | concise feature order | manual presentation | [Reviewer guide](REVIEWER_GUIDE.md) | Implemented; manual verification required |

## Required hand-ins

| Required hand-in | Location or command |
|---|---|
| Working code | [`backend/app`](../backend/app/) and [`frontend/src`](../frontend/src/) |
| Exact output CSV | [`backend/data/output/final_submission.csv`](../backend/data/output/final_submission.csv) |
| Short README | [`README.md`](../README.md) |
| Three-run evidence | [Reproducibility](REPRODUCIBILITY.md) and the machine manifest |
| Token/cost log | [Token and cost report](TOKEN_AND_COST_REPORT.md) and machine report |
| Ten-minute path | [Reviewer guide](REVIEWER_GUIDE.md) |

The supplied input CSVs are included for the case-study evaluation. Confirm the
challenge owner's redistribution terms before making the repository broadly public.
