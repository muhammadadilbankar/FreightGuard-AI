# FreightGuard AI

FreightGuard AI is an evidence-first freight-cost anomaly investigation system.
It will combine deterministic weekly cost analysis with strictly validated context
evidence so every result is reproducible and auditable.

## Status

Phase 11 (React investigation dashboard) is implemented. The repository provides a typed,
single-worker API over strict CSV ingestion, deterministic weekly
route metrics, leak-free own-history and self-excluding peer baselines, full-
precision percentage comparisons, configurable candidate detection, and an exact
eight-column preliminary CSV. It also compiles source context notes into immutable,
versioned evidence claims, discovers candidate evidence with local hybrid retrieval,
and applies deterministic validity gates before producing reviewed decisions. A
provider-independent wording layer now produces strictly validated explanations or
safe deterministic fallbacks without changing any canonical decision. Formal
three-run evaluation gates atomic publication of immutable API snapshots. The React
dashboard consumes that contract without recomputing canonical values, guards against
mixed snapshots, and provides a responsive, accessible investigation workflow.

The unchanged challenge CSV files are stored in `backend/data/input/`. Their
recorded byte sizes and SHA-256 hashes are documented in
`docs/INPUT_DATA_INTEGRITY.md`.

## Prerequisites

- Python 3.11 or newer
- `pip`
- Node.js 20.19 or newer and `npm` for the Phase 11 dashboard

## Setup

From the repository root, create and activate a virtual environment.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-dev.txt
Copy-Item .env.example .env
```

macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-dev.txt
cp .env.example .env
```

The checked-in defaults are safe for local development, so creating `.env` is
optional. A real `.env` is ignored by Git.

## Verify and run

```bash
python -m pytest backend/tests -q
python -m ruff check backend
python -m backend.scripts.validate_inputs
python -m backend.scripts.inspect_weekly_metrics
python -m backend.scripts.inspect_baselines
python -m backend.scripts.generate_candidate_output
python -m backend.scripts.compile_context_notes
python -m backend.scripts.prepare_embedding_model
python -m backend.scripts.review_candidate_evidence
python -m backend.scripts.generate_final_submission
python -m backend.scripts.evaluate_pipeline
python -m backend.scripts.run_api
```

In a second terminal, start the dashboard:

```bash
cd frontend
npm install
npm run dev
```

The API defaults to <http://127.0.0.1:8000> and the Vite development UI to
<http://127.0.0.1:5173>. See `frontend/README.md` for frontend verification and
environment configuration.

The validation command reads the three files under `backend/data/input/`, reports
one deterministic summary per dataset, and writes nothing. A successful run ends
with output equivalent to:

```text
context_notes.csv: valid (10 rows, 4 source columns)
sample_output_format_v2.csv: valid (8 header columns, 3 illustrative rows, 1 warning)
shipment_records.csv: valid (2940 rows, 10 source columns)
Result: PASS
```

The warning identifies an illustrative sample-output row containing an unquoted
comma. The exact eight-column header remains authoritative and the supplied file is
not repaired or rewritten.

The inspection command consumes the validated in-memory shipment frame and prints:

```text
Validated shipments: 2940
Weekly route groups: 728
Directional routes: 7
Route types: 3
Distinct weeks: 104
week_of range: 2024-01-01 to 2025-12-22
Reconciliation: PASS
```

For each `route + route_type + week_of`, the canonical weekly rate is:

```text
sum(freight_cost_inr) / sum(quantity_tonnes * distance_km)
```

The numerator and denominator are aggregated before division. This is intentionally
not the mean of shipment-level rates. Canonical totals and rates remain numeric and
unrounded; display formatting belongs to a later export or UI phase.

For each route and route type, the own-history baseline is the arithmetic mean of
at most the previous eight available observed route weeks. The current week is
shifted out before rolling; missing calendar weeks are neither synthesized nor
padded. The first observation therefore has a missing baseline and a
`history_weeks_used` value of zero.

The peer baseline is the unweighted arithmetic mean of other route-level rates with
the same route type and week. The current route is excluded. If no peer exists, the
baseline remains numerically missing and `peer_routes_used` is zero.

The baseline inspection command reports:

```text
Weekly route groups: 728
Own-history baselines available: 721
Own-history baselines unavailable: 7
Rows using full 8-week history: 672
Peer baselines available: 728
Peer baselines unavailable: 0
Peer routes used: min 1, max 2
No-look-ahead checks: PASS
Self-exclusion checks: PASS
```

Phase 5 calculates these unrounded percentage deviations:

```text
vs_own_history_pct = (current cost / own-history baseline - 1) * 100
vs_similar_routes_pct = (current cost / peer baseline - 1) * 100
```

The configured threshold defaults to `20.0` percent because the challenge does not
prescribe one. It can be changed with `ANOMALY_THRESHOLD_PERCENT`. The exact rule is:

```text
candidate = own deviation is available and > 0
            and (own deviation >= threshold
                 or available peer deviation >= threshold)
```

Threshold comparisons use full-precision values; one- and two-decimal formatting is
applied only to the generated display fields. A missing own baseline remains missing
and prevents a candidate decision because rising movement cannot be established. A
missing peer baseline remains missing and evaluates only the peer rule component as
false, so a sufficiently elevated own-history comparison may still qualify.

Generate the preliminary candidate output from the repository root with:

```bash
python -m backend.scripts.generate_candidate_output
```

The supplied data evaluates 728 route-week groups and produces 19 candidate rows in
`backend/data/output/candidate_anomalies.csv`. The file uses the authoritative exact
eight-column header, deterministic ordering and bytes, RFC-compliant quoting, and is
read back for contract validation after an atomic write. Generated output remains
ignored by Git.

This is deliberately a preliminary Phase 5 artifact: context notes have not been
evaluated. Every candidate is therefore `flagged = Yes`, every `matched_note_id` is
blank, and the reason states that context review is pending. It is not a final
evidence-reviewed submission.

Phase 6 deterministically compiles the validated context-note frame and an explicitly
injected seven-route universe into typed claims. Each claim preserves the source
text and records route scope, an inclusive effective interval, event type, cost-
impact status, impact direction, negation, an exact magnitude phrase when present,
and stable warning codes. Run it with:

```bash
python -m backend.scripts.compile_context_notes
```

The supplied data compiles all 10 notes and writes the schema-versioned diagnostic
artifact to `backend/data/output/compiled_context_notes.jsonl`. The file is sorted
by note ID, written atomically with deterministic JSON encoding, and validated by
an independent typed readback.

Transport-cost uncertainty is intentionally three-valued. Explicit increases or
decreases derive `affects_transport_cost = true`; explicit no-impact, no-rate-change,
or stable-operation claims derive `false`; and unstated or unresolved impact remains
JSON `null`, never a guessed `false`. Explicit negation is evaluated before positive
cost keywords.

Compiled claims are not accepted evidence, candidate-note matches, or final
verdicts. Phase 6 does not alter `candidate_anomalies.csv`; retrieval and the strict
Evidence Gate own those decisions in Phase 7.

Phase 7 uses two discovery channels: deterministic TF-IDF sparse retrieval and a
revision-pinned, CPU-only Sentence Transformers model. Weighted Reciprocal Rank
Fusion combines their ranks, while exact route/time structured recall ensures a
low-similarity but structurally applicable note still reaches validation. Similarity
only discovers notes; it never decides whether evidence is valid.

Prepare the pinned model explicitly, then run the review from the repository root:

```bash
python -m backend.scripts.prepare_embedding_model
python -m backend.scripts.review_candidate_evidence
```

The second command is local-only by default. It checks dataset scope, exact route
direction, inclusive date overlap, explicit transport-cost increase, impact
direction, negation, and explanatory scope. Exact-route evidence can fully justify
a candidate. Global evidence remains partial for a peer-driven anomaly because it
cannot explain why one route is more expensive than comparable routes. A justified
decision clears the flag and populates `matched_note_id`; partial or rejected-only
evidence leaves the candidate flagged.

The supplied data produces 19 decisions: 3 justified, 12 partially explained, and
4 unexplained. The validated outputs are:

- `backend/data/output/evidence_gate_audit.jsonl`, which retains discovery metadata
  and every gate rejection reason.
- `backend/data/output/evidence_reviewed_anomalies.csv`, which preserves all 19
  candidates in the authoritative eight-column format.

Phase 8 consumes only those validated evidence packets. The model is a wording
component: it cannot recalculate values, change verdicts, select notes, or alter
flags. Requests contain only selected or accepted supporting evidence, and source
note text is isolated as untrusted JSON data.

Three modes are supported through `EXPLANATION_MODE`:

- `template` is the default, deterministic offline mode and needs no credentials.
- `live` uses the configured OpenAI Responses API model after a cache lookup. Set
  `EXPLANATION_MODEL` and `OPENAI_API_KEY`; model pricing remains optional external
  configuration.
- `replay` is network-free and requires a complete previously validated live cache.

Unexplained candidates never call a model. Live responses must pass strict schema,
identity, verdict, note-ID, numeric-grounding, wording, formatting, and length
validation. A refusal, provider failure, or invalid response uses the appropriate
deterministic fallback without a repair prompt. Only fully validated provider
responses enter the content-addressed cache; changing the prompt, model, response
schema, or grounded request changes the cache key.

Generate the final submission with:

```bash
python -m backend.scripts.generate_final_submission
```

The command reports provider attempts, cache hits, validation failures, provider-
reported token usage, and an estimated cost when date-stamped pricing rates are
configured. It writes:

- `backend/data/output/explanation_generation_audit.jsonl`
- `backend/data/output/final_submission.csv`

The supplied data remains 19 rows with 3 justified, 12 partially explained, and 4
unexplained decisions.

Phase 12 adds deterministic operational investigation leads for unexplained
anomalies without changing those verdicts. The reference window is the same prior
eight available route and route-type observations used by the own-history baseline;
it is not calendar-filled and never looks ahead. Transporter and material are
independent lenses over the same rate gap. Tonne-km shares and category rates use
the symmetric two-factor identity for shared categories, while categories appearing
or disappearing use explicit entry or exit effects. Each lens must satisfy:

```text
sum(category mix + rate + entry + exit effects) = current rate - own baseline
```

The lens totals are not additive. Seven descriptive operational metrics cover
shipment count, average load, tonne-weighted distance, tonnage, tonne-km, freight
per shipment, and shipments per 100 tonnes. Support labels describe sample coverage,
not causality. These patterns are not validated context evidence and cannot select
note IDs, alter flags, or change verdicts.

The atomic schema-versioned artifact is
`backend/data/output/operational_root_causes.json`. Inspect it without a model call
or file mutation:

```bash
python -m backend.scripts.inspect_root_causes --route "Delhi-Jaipur" --week-of 2024-11-11
```

The API exposes `GET /api/anomalies/{route}/{week_of}/root-cause`. The Cost
Courtroom lazily shows eligible results with a trust boundary, independent lenses,
reconstruction, accessible details, metrics, support, and caveats. Small samples,
descriptive association, and missing fuel, vehicle, invoice, contract, traffic, and
capacity data remain known limitations.

Phase 13 adds a read-only natural-language investigation assistant at
`POST /api/assistant/query`. Template mode is fully offline: an ordered deterministic
planner maps supported questions to a closed set of typed snapshot queries. Optional
live mode may only produce a plan; policy validation, data access, calculations,
verdicts, note IDs, citations, and final wording remain backend-owned and
deterministic. Ambiguous requests return explicit choices, unsupported or mutating
requests execute no tools, and stale conversation context is rejected.

The dashboard’s **Ask** button opens the assistant panel. It supports anomaly
explanation/list/ranking, route trends, evidence review, rejected evidence,
operational leads, snapshot summary, evaluation status, run metrics, and help.
Answers include snapshot-bound citations and preserve the boundary between accepted
context evidence and descriptive operational leads.

Assistant evaluation is part of the formal offline command below. Its 40-case
golden/adversarial fixture checks every intent, ambiguity, mutation attempts, and
prompt injection, with zero hosted calls.

Phase 9 adds an independent, gate-based evaluation and reproducibility harness. Run
the formal offline evaluation from the repository root with:

```bash
python -m backend.scripts.evaluate_pipeline --runs 3 --mode template
```

A formal PASS means every blocking input, mathematics, baseline, candidate,
compilation, retrieval, Evidence Gate, explanation, CSV, metamorphic, and
investigation-assistant check passed. It also means three fresh Python processes generated
byte-identical `final_submission.csv` files without network access. Live explanation
mode is deliberately forbidden; a frozen validated replay cache is the only formal
alternative to template mode.

Reports are written under `backend/data/output/evaluation/`:

- `evaluation_report.json` contains typed checks, metrics, and fingerprints.
- `evaluation_report.md` is the judge-readable summary and lists blocking failures.
- `reproducibility_manifest.json` records every run and canonical artifact hash.
- `runs/run_01` through `runs/run_03` retain isolated run artifacts.

For the supplied data, the expected headline results are 2,940 shipments, 728
weekly route groups, 19 candidates, 10 notes, a 3/12/4 verdict split, zero false
clearances, and zero unsafe evidence acceptances. When a run fails, inspect the
`Blocking failures` section of the Markdown report or the `checks` array in JSON,
then rerun the same command from a clean shell with the pinned local embedding model
available. Output paths, timeouts, logging, and secrets are excluded from the
configuration fingerprint; every setting capable of changing canonical content is
included.

With the API running, open <http://127.0.0.1:8000/health>. It reports liveness and
readiness without forcing analysis. Use `POST /api/analysis/run` to publish the
first snapshot, then inspect the typed endpoints through <http://127.0.0.1:8000/docs>.
The service must run with one worker; see `docs/API.md` for its endpoint and failure
contracts.

## Project structure

```text
backend/app/          API, application state, domain contracts, and trusted services
backend/data/input/   Unmodified challenge inputs (supplied separately)
backend/data/output/  Generated artifacts from future phases
backend/scripts/      Local validation commands
backend/tests/        Backend tests
docs/                 Product specification, roadmap, and decision log
frontend/             React investigation dashboard, tests, and generated API types
```
