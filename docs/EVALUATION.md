# Evaluation

## Goals and design

The formal harness independently checks input integrity, mathematics, candidates,
note compilation, retrieval, evidence decisions, grounded explanations,
operational analysis, the final CSV, metamorphic invariants, the assistant, and
three-run reproducibility. Expected candidates, compiled notes, evidence decisions,
adversarial notes, and 40 assistant questions are versioned test fixtures.

## Coverage

| Evaluation criterion | Evidence |
|---|---|
| Core logic | Aggregation, baseline, comparison, candidate, and output checks |
| Meaningful AI | Retrieval quality and constrained explanation tests |
| Trust | Evidence Gate, negative controls, grounding, and injection tests |
| Repeatability | Three isolated subprocess runs and artifact comparisons |
| Responsible operation | Provider-call/token records and bounded modes |
| Code quality | Typed contracts, Ruff, unit/integration/UI tests, and docs |

Mathematical checks independently recompute weighted weekly cost and both
baselines. Evidence checks cover accepted and rejected notes, wrong-route/date,
direction, negation, cost impact, global scope, false clearance, and unsafe
acceptance. Output checks validate the exact schema, quoting, ordering, note-ID
behavior, and negative controls.

The assistant fixture covers every intent plus direct/paraphrased wording, filters,
ranking, ambiguity, unsupported prediction, mutation, secret extraction, and prompt
injection. Every substantive answer claim must resolve to a snapshot citation.

## Commands

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m backend.scripts.evaluate_pipeline --runs 3 --mode template
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run test:e2e
```

## Latest verified result

The current schema-1.2 formal report is **PASS**: 109 of 109 checks passed across
13 domains, with 36 recorded metrics. False-clearance and unsafe-evidence-
acceptance rates were both 0%. The assistant domain passed all 18 blocking checks
with zero provider calls. See the
[machine report](../backend/data/output/evaluation/evaluation_report.json).

The final backend regression run passed 352 tests; one credentials-dependent live
provider smoke test was skipped. Frontend verification passed 14 component tests,
12 desktop/tablet/mobile Playwright tests, strict typechecking, lint, and the
production build.

## Coverage gaps

Formal evaluation uses the deterministic template mode. Live-provider smoke tests
are optional and skipped without credentials. The supplied dataset is small, does
not provide production labels for fraud, and cannot validate causal claims or
external events. Browser tests use controlled API fixtures; backend supplied-data
integration tests cover the real pipeline artifacts.
