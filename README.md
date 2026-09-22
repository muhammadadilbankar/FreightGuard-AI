# FreightGuard AI

FreightGuard AI is an evidence-first freight-cost anomaly investigation system.
It will combine deterministic weekly cost analysis with strictly validated context
evidence so every result is reproducible and auditable.

## Status

Phase 5 (candidate detection and preliminary output) is implemented. The repository
provides a typed FastAPI foundation, strict CSV ingestion, deterministic weekly
route metrics, leak-free own-history and self-excluding peer baselines, full-
precision percentage comparisons, configurable candidate detection, and an exact
eight-column preliminary CSV. Context evidence, final verdicts, AI wording, and the
dashboard belong to later phases and are not implemented yet.

The unchanged challenge CSV files are stored in `backend/data/input/`. Their
recorded byte sizes and SHA-256 hashes are documented in
`docs/INPUT_DATA_INTEGRITY.md`.

## Prerequisites

- Python 3.11 or newer
- `pip`

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
python backend/run.py
```

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

With the API running, open <http://127.0.0.1:8000/health>. It returns service
status, name, version, and environment without reading shipment data or calling an
external service.

## Project structure

```text
backend/app/          FastAPI application, configuration, schemas, routes, ingestion
backend/data/input/   Unmodified challenge inputs (supplied separately)
backend/data/output/  Generated artifacts from future phases
backend/scripts/      Local validation commands
backend/tests/        Backend tests
docs/                 Product specification, roadmap, and decision log
frontend/             Placeholder for the later dashboard phase
```
