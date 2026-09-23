# FreightGuard API

The API is a process-local, single-worker delivery layer over the validated
analysis pipeline. It starts alive but not ready. Publish the first immutable
snapshot with `POST /api/analysis/run`; reads return `503 analysis_not_ready` until
that run succeeds. A failed refresh never replaces the previous snapshot.

## Run locally

First generate a passing formal report for the current inputs and deterministic
configuration:

```powershell
.\.venv\Scripts\python.exe -m backend.scripts.evaluate_pipeline --runs 3 --mode template
.\.venv\Scripts\python.exe -m backend.scripts.run_api
```

OpenAPI is available locally at `http://127.0.0.1:8000/docs` and
`http://127.0.0.1:8000/openapi.json`. Keep exactly one Uvicorn worker because the
active snapshot and run coordinator are process-local.

## Endpoints

- `GET /health` — liveness, readiness, run state, and active snapshot ID.
- `POST /api/analysis/run` — run, validate, and atomically publish.
- `GET /api/analysis/summary` — counts and analysis coverage.
- `GET /api/anomalies` — exact filters, allowlisted sorting, and pagination.
- `GET /api/anomalies/{route}/{week_of}` — candidate and evidence detail.
- `GET /api/anomalies/{route}/{week_of}/root-cause` — operational decomposition
  for unexplained anomalies.
- `GET /api/routes/{route}/timeline` — chronological weekly route data.
- `GET /api/evaluation/report` — formal report bound to the snapshot.
- `GET /api/run-metrics` — operational metrics and latest-attempt status.
- `GET /api/analysis/export.csv` — exact validated CSV bytes with an ETag.
- `POST /api/assistant/query` — bounded read-only snapshot investigation.

JSON data endpoints use `{ "data": ..., "meta": ... }`. Handled failures use
`{ "error": { "code", "message", "details", "request_id" } }`. Every response
returns `X-Request-ID`; unsafe request IDs are replaced.

## Investigation assistant

The assistant accepts a question, optional planner mode, and optional typed context.
It returns `answered`, `needs_clarification`, or `unsupported`, plus grounded
claims, citations, optional tables, navigation actions, and planner telemetry.
Template mode makes no network calls. Stale snapshot context is rejected. No mode
can mutate an anomaly, verdict, note match, output, or threshold.

## Configuration and operation

`API_ALLOWED_ORIGINS` is an exact-origin list. Auto-run is disabled by default.
Live explanations require both explicit API enablement and provider configuration.
Requests and pages are bounded by configured limits. Authentication, a database,
multi-process snapshot sharing, background jobs, uploads, and public deployment are
outside the local evaluator scope. Temporary API-run artifacts are ignored by Git.
