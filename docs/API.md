# FreightGuard Phase 10 API

The API is a process-local, single-worker delivery layer over the validated Phase
2–9 pipeline. It starts alive but not ready. Publish the first immutable snapshot
with `POST /api/analysis/run`; reads return `503 analysis_not_ready` until that run
succeeds. A failed refresh never replaces the previous snapshot.

## Run locally

First generate a passing Phase 9 report for the current inputs and deterministic
configuration:

```bash
python -m backend.scripts.evaluate_pipeline
python -m backend.scripts.run_api
```

OpenAPI is available at `http://127.0.0.1:8000/docs` and
`http://127.0.0.1:8000/openapi.json`. Keep exactly one Uvicorn worker because the
active snapshot and run coordinator are intentionally process-local.

## Endpoints

- `GET /health` — liveness, readiness, run state, and active snapshot ID.
- `POST /api/analysis/run` — synchronously run, validate, and atomically publish.
- `GET /api/analysis/summary` — dashboard counts and analysis coverage.
- `GET /api/anomalies` — exact filters, allowlisted sorting, and bounded pagination.
- `GET /api/anomalies/{route}/{week_of}` — candidate and safe evidence detail.
- `GET /api/anomalies/{route}/{week_of}/root-cause` — snapshot-backed operational
  decomposition for unexplained anomalies (`409` when not applicable and `422`
  when unavailable).
- `GET /api/routes/{route}/timeline` — chronological weekly route data.
- `GET /api/evaluation/report` — the in-memory Phase 9 report for the snapshot.
- `GET /api/run-metrics` — safe operational metrics and latest-attempt status.
- `GET /api/analysis/export.csv` — exact validated CSV bytes with an ETag.

JSON data endpoints use `{ "data": ..., "meta": ... }`. Handled failures use
`{ "error": { "code", "message", "details", "request_id" } }`. Every response
returns `X-Request-ID`; request IDs with control characters or more than 128
characters are replaced.

## Configuration and operation

`API_ALLOWED_ORIGINS` is a comma-separated exact-origin list and defaults to the
Phase 11 development origin. `API_AUTO_RUN_ON_STARTUP=false` is the safe default.
Live explanation requests also require `API_LIVE_EXPLANATIONS_ENABLED=true` and
the Phase 8 provider configuration. Request bodies are bounded by
`API_MAX_REQUEST_BYTES`; collection pages are bounded by `API_MAX_PAGE_SIZE`.

Phase 10 deliberately does not add authentication, a database, multi-process
snapshot sharing, background jobs, uploads, Docker, or the frontend. Generated run
artifacts are private under `backend/data/output/api_runs/<attempt-id>/` and are
ignored by Git.
# Investigation assistant

`POST /api/assistant/query` accepts a question, optional planner mode, and optional
typed conversation context. It reads exactly one active immutable snapshot and
returns a status (`answered`, `needs_clarification`, or `unsupported`), grounded
claims, optional table, citations, navigation actions, updated context, and planner
telemetry. Template mode is the default and makes no network calls.

Conversation context is client-owned and includes its snapshot ID. Context from an
older snapshot is rejected with `request_validation_failed`; clients should clear it
when the active snapshot changes. Live planning is disabled unless explicitly
allowed and configured. No mode can mutate an anomaly, verdict, note match, output,
or threshold.
