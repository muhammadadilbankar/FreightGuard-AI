# FreightGuard AI - Phase 1 Repository Foundation Implementation Plan

## 1. Purpose of this document

This document is the complete implementation contract for Phase 1 of FreightGuard AI. Give it to Codex together with the master roadmap and ask Codex to implement this phase only.

Phase 1 establishes a clean, testable project foundation. It deliberately does not implement shipment analytics, baselines, anomaly detection, retrieval, AI generation, or the frontend.

## 2. Phase objective

Create a production-quality repository foundation containing:

- A structured Python backend
- FastAPI application bootstrap
- Typed settings management
- Structured logging
- Health-check endpoint
- Pytest setup
- Input and output data directories
- Supplied challenge files in the input directory
- Initial documentation
- Environment-variable template
- Repository-wide Codex instructions

After Phase 1, a developer should be able to clone the repository, install dependencies, run tests, start the API, and verify the health endpoint.

## 3. Required project structure

Create the following structure unless an equivalent structure already exists:

```text
freightguard-ai/
├── AGENTS.md
├── README.md
├── .env.example
├── .gitignore
├── docs/
│   ├── PROJECT_SPEC.md
│   ├── IMPLEMENTATION_PLAN.md
│   └── DECISIONS.md
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── health.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   └── logging.py
│   │   ├── models/
│   │   │   └── __init__.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── health.py
│   │   └── services/
│   │       └── __init__.py
│   ├── data/
│   │   ├── input/
│   │   │   ├── shipment_records.csv
│   │   │   ├── context_notes.csv
│   │   │   └── sample_output_format_v2.csv
│   │   └── output/
│   │       └── .gitkeep
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_config.py
│   │   └── test_health.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pytest.ini
│   └── run.py
└── frontend/
    └── README.md
```

The `frontend` directory is only a placeholder in this phase. Do not initialize React yet.

## 4. Dependency requirements

Use a minimal dependency set.

### Runtime dependencies

```text
fastapi
uvicorn[standard]
pydantic
pydantic-settings
python-dotenv
```

### Development dependencies

```text
pytest
pytest-cov
httpx
ruff
```

Pin dependencies to compatible versions using a consistent versioning strategy. Do not add Pandas, FAISS, sentence-transformers, LLM SDKs, databases, Docker dependencies, or frontend packages during Phase 1.

## 5. Application configuration

Implement a typed settings class using `pydantic-settings`.

Minimum settings:

```text
APP_NAME=FreightGuard AI API
APP_ENV=development
APP_VERSION=0.1.0
HOST=127.0.0.1
PORT=8000
LOG_LEVEL=INFO
INPUT_DATA_DIR=backend/data/input
OUTPUT_DATA_DIR=backend/data/output
ANOMALY_THRESHOLD_PERCENT=20.0
```

Requirements:

- Load optional values from `.env`.
- Provide safe development defaults.
- Resolve paths predictably regardless of the shell's current working directory.
- Never commit a real `.env` file.
- Include every supported setting in `.env.example`.
- Validate that the anomaly threshold is non-negative.
- Do not use the threshold for analytics yet.

## 6. FastAPI application requirements

Create an application factory or equivalent clean bootstrap mechanism.

The FastAPI application must expose:

```text
GET /health
```

Expected response shape:

```json
{
  "status": "ok",
  "service": "FreightGuard AI API",
  "version": "0.1.0",
  "environment": "development"
}
```

Requirements:

- Response must be validated by a Pydantic response schema.
- Endpoint must not access shipment data.
- Endpoint must not depend on an external service.
- Endpoint should return HTTP 200 when the application is running.
- Keep route definitions outside `main.py`.
- Use the application's configured name and version rather than duplicating literals.

## 7. Logging requirements

Create a small logging setup that:

- Uses Python's standard `logging` library.
- Reads the level from settings.
- Uses a consistent timestamped format.
- Avoids duplicate handlers during tests or reloads.
- Does not log environment secrets.
- Is initialized during application startup.

Do not build a complex logging framework in this phase.

## 8. Challenge data handling

Place exact copies of the supplied files in `backend/data/input/`:

```text
shipment_records.csv
context_notes.csv
sample_output_format_v2.csv
```

Requirements:

- Do not alter content, filenames, ordering, encoding, or line endings intentionally.
- Record SHA-256 hashes before and after copying and confirm they match.
- Do not parse or clean the CSV files during Phase 1.
- Generated output must eventually go under `backend/data/output/`.
- Keep generated output files ignored by Git while preserving the empty directory with `.gitkeep`.

If the files are not available in the current repository or accessible input location, Codex must create the directory structure, report the missing files, and stop short of inventing replacements.

## 9. Testing requirements

Configure Pytest and implement focused tests.

### 9.1 Health endpoint tests

Test that:

- `GET /health` returns HTTP 200.
- Response matches the required schema.
- `status` equals `ok`.
- Service name, version, and environment come from settings.

### 9.2 Configuration tests

Test that:

- Default settings load successfully.
- Environment variables override defaults.
- Negative anomaly thresholds are rejected.
- Input and output paths resolve consistently.

### 9.3 Smoke-import test

At minimum, verify that the application can be imported without starting a server or connecting to any external dependency.

### 9.4 Test isolation

- Tests must not read or modify the supplied shipment data.
- Tests must not require internet access.
- Tests must not depend on a developer's local `.env` file.
- Override environment values safely using Pytest fixtures or monkeypatching.

## 10. `run.py` requirements

Provide a simple local entry point so the backend can be started from the project root using:

```bash
python backend/run.py
```

It should start Uvicorn using configured host, port, and log level.

Development reload may be enabled only when the environment is `development`. Avoid behaviour that causes recursive process spawning on unsupported systems.

## 11. README requirements

Create an initial repository README containing:

1. Project name and one-paragraph purpose
2. Current implementation status: Phase 1 foundation
3. Prerequisites
4. Virtual-environment setup
5. Dependency installation
6. Environment setup using `.env.example`
7. Commands to run tests
8. Command to start the API
9. Health endpoint URL
10. High-level project structure
11. Brief statement that later phases will add analytics, evidence retrieval, and the dashboard

Do not claim that anomaly detection or AI functionality already exists.

Provide both Windows PowerShell and Unix-style setup commands when they differ materially.

## 12. `AGENTS.md` requirements

Create a repository-level `AGENTS.md` containing these rules:

- Read project documentation before editing.
- Work on only the requested phase.
- Inspect existing code before changes.
- Do not hardcode sample anomalies or note IDs.
- Keep deterministic math separate from AI.
- An LLM must never decide canonical numbers, matched note IDs, or final verdicts.
- Add and run tests for every phase.
- Use sensible timeouts for long-running commands.
- Do not begin the next phase automatically.
- Report changed files, test results, manual verification steps, limitations, and a suggested commit message.
- Never commit secrets or a real `.env` file.
- Do not rewrite unrelated user changes.

Include the mathematical contract by reference to `docs/PROJECT_SPEC.md`; it does not need to be duplicated fully inside `AGENTS.md`.

## 13. Documentation files

### `docs/PROJECT_SPEC.md`

Include:

- Business problem
- Required inputs and output
- Mathematical contract
- Candidate anomaly rule
- Evidence-validation rules
- Reproducibility requirements
- Core product principles

### `docs/IMPLEMENTATION_PLAN.md`

Copy or adapt the master implementation roadmap so every later phase remains visible to Codex.

### `docs/DECISIONS.md`

Start an Architecture Decision Log containing at least:

```text
ADR-001: Use weighted aggregate cost per tonne-km
ADR-002: Separate deterministic decisions from AI wording
ADR-003: Use Monday as week_of
ADR-004: Keep anomaly threshold configurable
ADR-005: Delay frontend and AI dependencies until later phases
```

For each decision, include status, context, decision, and consequences.

## 14. `.gitignore` requirements

Ignore at least:

```text
.env
.venv/
venv/
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
.ruff_cache/
backend/data/output/*
!backend/data/output/.gitkeep
node_modules/
dist/
.DS_Store
Thumbs.db
```

Do not ignore the supplied challenge input files.

## 15. Quality requirements

- Use type hints for public functions.
- Use concise docstrings where behaviour is not obvious.
- Keep API routes thin.
- Avoid global mutable state.
- Avoid premature abstraction.
- Use clear imports that work from the documented run commands.
- Do not suppress errors broadly.
- Do not install or call external services.
- Preserve unrelated repository files and user changes.

## 16. Explicit non-goals for Phase 1

Codex must not implement any of the following:

- CSV parsing or validation logic
- Pandas transformations
- Weekly aggregation
- Historical or peer baselines
- Anomaly detection execution
- Output CSV generation
- Context-note parsing
- Embeddings or vector search
- LLM providers
- Token or cost tracking
- SQLite or another database
- React or Vite initialization
- Dockerfiles or Docker Compose
- Authentication
- File-upload endpoints
- Natural-language Q&A

Configuration placeholders are allowed, but no later-phase business logic should be added.

## 17. Required verification commands

Codex must adapt these commands to the final repository layout and operating system, then report the exact commands that succeeded.

### Install

```bash
python -m venv .venv
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-dev.txt
```

### Tests

```bash
python -m pytest backend/tests -q
```

### Lint

```bash
python -m ruff check backend
```

### Run API

```bash
python backend/run.py
```

### Manual health check

```bash
curl http://127.0.0.1:8000/health
```

Long-running server verification must use a controlled background process or timeout. Codex must not leave a command waiting indefinitely.

## 18. Acceptance criteria

Phase 1 is complete only when all of the following are true:

- [x] Required repository structure exists.
- [x] Runtime and development dependency files exist.
- [x] Typed settings load successfully.
- [x] `.env.example` documents every supported setting.
- [x] Real `.env` files are ignored.
- [x] FastAPI application imports successfully.
- [x] `GET /health` returns HTTP 200 and the expected JSON structure.
- [x] Logging is initialized without duplicate handlers.
- [x] Supplied CSV files are present without modification and have recorded hashes.
- [x] Output directory exists and preserves `.gitkeep`.
- [x] Configuration tests pass.
- [x] Health endpoint tests pass.
- [x] Test suite does not require internet access.
- [x] Ruff reports no errors in the backend.
- [x] README setup and run instructions are accurate.
- [x] `AGENTS.md` and all three project documents exist.
- [x] No Phase 2 or later functionality was implemented.
- [x] Codex reports all changed files and commands executed.
- [x] Codex suggests a Git commit message and stops.

The three challenge CSV files were supplied directly in the canonical input
directory. Their byte sizes and SHA-256 hashes were recorded before and after the
final Phase 1 verification; both measurements matched exactly. See
`docs/INPUT_DATA_INTEGRITY.md`.

## 19. Suggested Phase 1 commit message

```text
chore: establish FreightGuard backend foundation
```

## 20. Copy-paste instruction for Codex

```text
Read AGENTS.md, FREIGHTGUARD_MASTER_IMPLEMENTATION_ROADMAP.md,
FREIGHTGUARD_PHASE_1_FOUNDATION_PLAN.md, and all existing files under docs/
completely before editing.

Inspect the repository and preserve all unrelated existing work.

Implement Phase 1 only according to
FREIGHTGUARD_PHASE_1_FOUNDATION_PLAN.md.

Do not implement data ingestion, analytics, anomaly detection, retrieval,
LLM functionality, React, or Docker. Do not hardcode sample routes, anomalies,
or note IDs.

Use the supplied challenge files without modifying their contents. Verify file
integrity when copying them into the project input directory.

Add the required tests and run them with sensible timeouts. Run the configured
linter. Verify the API health endpoint without leaving a server process running.

When finished, report:

1. What was implemented
2. Every file created or modified
3. Engineering decisions made
4. Commands executed and their results
5. Exact manual verification instructions
6. Any limitations or blockers
7. A concise Git commit message

Update the Phase 1 checklist, then stop. Do not begin Phase 2.
```
