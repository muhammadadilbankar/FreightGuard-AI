# FreightGuard AI

FreightGuard AI is an evidence-first freight-cost anomaly investigation system.
It will combine deterministic weekly cost analysis with strictly validated context
evidence so every result is reproducible and auditable.

## Status

Phase 3 (weekly cost analytics) is implemented. The repository provides a typed
FastAPI foundation, strict CSV ingestion, copy-based normalization, and deterministic
weekly route metrics with reconciliation audit fields. Historical and peer
baselines, anomaly flags, evidence retrieval, AI wording, and the dashboard belong
to later phases and are not implemented yet.

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
