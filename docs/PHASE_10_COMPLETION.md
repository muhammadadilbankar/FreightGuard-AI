# Phase 10 completion record

Phase 10 is complete for the single-process deployment model defined by the plan.

- [x] Import-safe application factory, explicit lifespan, settings, CORS, request IDs, and safe errors.
- [x] Immutable snapshots, atomic replacement, non-blocking one-run coordinator, and old-snapshot preservation.
- [x] Pipeline work runs off the async event loop and publishes only when the matching Phase 9 report passes.
- [x] Health, run, summary, anomaly list/detail, timeline, evaluation, metrics, and exact CSV export endpoints.
- [x] Typed request/response contracts, bounded pagination, exact matching, Monday dates, and allowlisted sorting.
- [x] OpenAPI, unit/API/concurrency tests, and a real supplied-data integration test.
- [x] Single-worker run command and operator/API documentation.

Verification on the supplied data produced 2,940 shipments, 728 weekly records,
19 candidates, the 3/12/4 verdict distribution, a passing evaluation, zero hosted
model calls in template mode, and byte-identical export content.

Intentional boundary: snapshots and locking are process-local, so `API_WORKERS` is
validated as exactly `1`. Authentication, persistence, background jobs, containers,
and the React dashboard remain outside Phase 10.
