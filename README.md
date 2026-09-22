# FreightGuard AI

FreightGuard AI is an evidence-first freight-cost anomaly investigation system.
It will combine deterministic weekly cost analysis with strictly validated context
evidence so every result is reproducible and auditable.

## Status

Phase 1 (repository foundation) is implemented. The repository currently provides
a typed FastAPI service, structured logging, configuration, and a health endpoint.
Shipment analytics, anomaly detection, evidence retrieval, AI wording, and the
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
python backend/run.py
```

With the API running, open <http://127.0.0.1:8000/health>. It returns service
status, name, version, and environment without reading shipment data or calling an
external service.

## Project structure

```text
backend/app/          FastAPI application, configuration, schemas, and routes
backend/data/input/   Unmodified challenge inputs (supplied separately)
backend/data/output/  Generated artifacts from future phases
backend/tests/        Backend tests
docs/                 Product specification, roadmap, and decision log
frontend/             Placeholder for the later dashboard phase
```
