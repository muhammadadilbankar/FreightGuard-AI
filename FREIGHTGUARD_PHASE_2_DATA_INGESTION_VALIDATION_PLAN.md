# FreightGuard AI - Phase 2 Data Ingestion and Validation Implementation Plan

## 1. Purpose of this document

This document is the complete implementation contract for Phase 2 of FreightGuard AI. Give it to Codex together with the master implementation roadmap after Phase 1 has been completed and verified.

Phase 2 adds strict, deterministic loading, validation, and normalization for the supplied challenge files. It does not calculate weekly costs, baselines, anomalies, contextual verdicts, embeddings, or AI explanations.

## 2. Phase objective

Build a trustworthy ingestion boundary that:

- Loads the supplied shipment and context-note CSV files without altering them.
- Validates structural, type, domain, uniqueness, and business-safety constraints.
- Produces a normalized in-memory working copy for later analytical phases.
- Derives `route`, `week_of`, and `tonne_km` for every valid shipment.
- Reads the sample-output header as the authoritative submission contract.
- Collects useful validation errors rather than failing with an unhelpful Pandas traceback.
- Provides a local validation command and machine-testable services.
- Preserves deterministic row ordering and source traceability.

After Phase 2, later services should be able to request a validated `InputBundle` instead of reading CSV files directly.

## 3. Preconditions

Before implementation, Codex must verify that Phase 1 is complete:

- The backend application imports successfully.
- `GET /health` passes its tests.
- Typed settings exist and expose the configured input/output directories.
- Pytest and Ruff are configured.
- The supplied challenge files exist under the configured input directory.
- The project documentation and `AGENTS.md` exist.
- The Git working tree is inspected so unrelated user changes are preserved.

If Phase 1 is materially incomplete, Codex must report the blocker instead of rebuilding the project or silently changing the architecture.

## 4. Supplied input contracts

## 4.1 `shipment_records.csv`

Required columns:

```text
shipment_id
origin
destination
route_type
material
quantity_tonnes
distance_km
freight_cost_inr
shipment_date
transporter
```

Expected semantic types:

| Column | Working type | Validation rules |
|---|---|---|
| `shipment_id` | string | Required, non-blank, unique |
| `origin` | string | Required, non-blank |
| `destination` | string | Required, non-blank |
| `route_type` | constrained string | Exactly `Short`, `Medium`, or `Long` |
| `material` | string | Required, non-blank |
| `quantity_tonnes` | floating point | Finite and strictly greater than zero |
| `distance_km` | floating point | Finite and strictly greater than zero |
| `freight_cost_inr` | numeric | Finite and strictly greater than zero |
| `shipment_date` | date | Strictly parseable as `YYYY-MM-DD` |
| `transporter` | string | Required, non-blank |

The loader must reject duplicate column names, missing required columns, and unexpected columns by default. Column order may differ, but the returned working frame must be reordered into the canonical order above before derived fields are appended.

## 4.2 `context_notes.csv`

Required columns:

```text
note_id
date
applies_to
note
```

Expected semantic types:

| Column | Working type | Validation rules |
|---|---|---|
| `note_id` | string | Required, non-blank, unique |
| `date` | date | Strictly parseable as `YYYY-MM-DD` |
| `applies_to` | string | Required, non-blank |
| `note` | string | Required, non-blank |

Phase 2 must not interpret the meaning, impact direction, effective interval, or causal strength of a context note. Semantic note compilation belongs to Phase 6.

## 4.3 `sample_output_format_v2.csv`

The authoritative output-header contract is:

```text
route
week_of
cost_per_tonne_km
vs_own_history
vs_similar_routes
flagged
matched_note_id
reason
```

Important supplied-file caveat:

Some sample rows contain commas inside natural-language fields without consistent RFC CSV quoting. A normal full-file Pandas parse can therefore report a different number of fields on some rows.

Required Phase 2 behaviour:

- Preserve the supplied file byte-for-byte.
- Read and validate the first CSV record as the authoritative column contract.
- Confirm that the header contains exactly the eight expected columns in the expected order.
- Do not treat malformed illustrative body rows as canonical application data.
- Optionally inspect body rows and return a non-blocking diagnostic warning when field counts are inconsistent.
- Do not rewrite, repair, or replace the supplied sample file.
- The real submission writer added in Phase 5 must use an RFC-compliant CSV writer.

## 5. Required project structure changes

Extend the Phase 1 structure without reorganizing unrelated files:

```text
backend/
├── app/
│   ├── schemas/
│   │   └── ingestion.py
│   └── services/
│       └── ingestion/
│           ├── __init__.py
│           ├── contracts.py
│           ├── errors.py
│           ├── loaders.py
│           ├── normalization.py
│           └── validation.py
├── scripts/
│   ├── __init__.py
│   └── validate_inputs.py
└── tests/
    ├── fixtures/
    │   ├── shipments_valid_minimal.csv
    │   ├── context_notes_valid_minimal.csv
    │   └── output_contract_valid.csv
    ├── unit/
    │   ├── test_shipment_validation.py
    │   ├── test_context_validation.py
    │   ├── test_normalization.py
    │   └── test_output_contract.py
    └── integration/
        └── test_supplied_inputs.py
```

Codex may adapt filenames to match an already-established equivalent convention, but responsibilities must remain separated:

- `contracts.py`: canonical filenames, columns, allowed values, and output header.
- `errors.py`: ingestion-specific exceptions.
- `loaders.py`: file access and orchestration.
- `validation.py`: pure structural and semantic validation.
- `normalization.py`: creation of normalized working copies and derived fields.
- `schemas/ingestion.py`: typed validation reports and summaries.
- `scripts/validate_inputs.py`: human-facing validation command.

Do not place all Phase 2 code in one large `utils.py` file.

## 6. Dependency changes

Add Pandas as a pinned runtime dependency compatible with the project's Python version and existing dependency strategy.

Do not add:

- Pandera
- Polars
- NumPy as a separately managed direct dependency unless the project explicitly requires it
- SQLAlchemy or a database
- FAISS
- Sentence Transformers
- LLM provider SDKs
- React dependencies

Pandas and the Python standard library are sufficient for this phase.

## 7. Ingestion domain models

Implement typed models for validation outcomes. Names may vary if the existing codebase has a consistent convention.

## 7.1 `ValidationSeverity`

Suggested values:

```text
error
warning
```

## 7.2 `ValidationIssue`

Suggested fields:

```text
severity
code
dataset
message
column: optional
row_number: optional
```

Requirements:

- `code` must be stable and machine-testable.
- `row_number` should refer to the human-visible CSV row when practical.
- Error messages should explain how to correct the problem.
- Do not dump full raw rows into logs or exceptions.

Suggested issue codes:

```text
file_not_found
file_not_readable
empty_file
duplicate_column
missing_column
unexpected_column
missing_value
blank_value
invalid_type
invalid_date
invalid_route_type
non_positive_value
non_finite_value
duplicate_identifier
invalid_output_header
malformed_sample_row
```

## 7.3 `ValidationReport`

Suggested fields:

```text
dataset
source_path
is_valid
row_count
errors
warnings
summary
```

The report must be deterministic: issues should be sorted by dataset, row number, column, and code before display or serialization.

## 7.4 `InputBundle`

Represent the validated in-memory result with a typed dataclass or similarly explicit container:

```text
shipments: pandas.DataFrame
context_notes: pandas.DataFrame
output_columns: tuple[str, ...]
reports: tuple[ValidationReport, ...]
```

Requirements:

- DataFrames in the bundle must be normalized copies, not aliases that mutate raw loaded frames unexpectedly.
- Only return an `InputBundle` when blocking validation errors are absent.
- Callers should not need to know individual input file paths.

## 8. Exception design

Implement a small exception hierarchy:

```text
IngestionError
├── InputFileError
└── DataValidationError
```

Requirements:

- `InputFileError` covers missing, unreadable, empty, or undecodable files.
- `DataValidationError` contains one or more structured validation issues.
- Collect independent validation failures so users can fix multiple problems in one pass.
- Do not expose raw Pandas tracebacks as the primary user-facing error.
- Preserve the original exception as the cause where useful.
- Do not use broad `except Exception: pass` handling.

## 9. File loading requirements

## 9.1 Common behaviour

All loaders must:

- Accept an explicit `Path` or obtain paths from settings through a top-level orchestration function.
- Resolve paths without depending on the current working directory.
- Open text files using UTF-8 with an explicit policy.
- Detect missing and empty files before processing.
- Avoid modifying source files.
- Avoid writing temporary corrected copies.
- Produce deterministic outputs for identical input bytes.
- Log filenames and counts, not full shipment or note contents.

## 9.2 Shipment loader

Recommended flow:

1. Confirm file existence and readability.
2. Detect empty input.
3. Read the CSV without allowing Pandas to silently coerce invalid identifiers.
4. Validate header shape and duplicate columns.
5. Validate missing values and semantic types.
6. Normalize a separate working copy.
7. Append derived fields.
8. Return the normalized DataFrame plus validation report.

Do not use permissive options such as silently skipping malformed rows.

## 9.3 Context-note loader

Follow the same structural approach as shipment loading. Preserve the original note text exactly in the returned `note` column except for type normalization required to represent it as a string. Do not summarize or rewrite note text.

## 9.4 Output-contract loader

Use the Python standard-library `csv` module or another header-safe approach. The first record is authoritative. Do not use a full-file Pandas parse as a prerequisite for accepting the header.

## 9.5 Bundle loader

Provide one public orchestration function, for example:

```python
def load_input_bundle(settings: Settings) -> InputBundle:
    ...
```

It must:

- Resolve all three configured files.
- Load and validate them through dedicated loaders.
- Aggregate blocking issues.
- Raise one structured error when any required dataset is invalid.
- Return the typed bundle when validation succeeds.

Later phases should call this function instead of using `pandas.read_csv` directly.

## 10. Shipment validation requirements

## 10.1 Header validation

- Reject duplicate column names.
- Reject missing required columns.
- Reject unexpected columns by default.
- Do not fail solely because valid columns appear in a different order.
- Reorder the valid working frame into canonical order.

## 10.2 Identifier validation

For `shipment_id`:

- Reject null values.
- Reject empty strings and whitespace-only values.
- Reject duplicates after safe string normalization.
- Preserve the canonical string value in the working copy.

## 10.3 Text validation

For `origin`, `destination`, `material`, and `transporter`:

- Reject null values.
- Reject empty or whitespace-only strings.
- Normalize leading and trailing whitespace only in the working copy.
- Preserve internal whitespace and original capitalization.
- Do not mutate the source file.

For `route_type`:

- Accept only exact canonical values: `Short`, `Medium`, `Long`.
- Do not silently convert unknown casing such as `short` into `Short`.
- Report the invalid row and value category without dumping the complete row.

## 10.4 Numeric validation

For `quantity_tonnes`, `distance_km`, and `freight_cost_inr`:

- Reject null values.
- Reject non-numeric values.
- Reject positive or negative infinity.
- Reject NaN.
- Reject zero.
- Reject negative values.
- Preserve sufficient precision for later calculations.

Do not round these columns during ingestion.

## 10.5 Date validation

For `shipment_date`:

- Require strict `YYYY-MM-DD` input.
- Reject impossible calendar dates.
- Convert valid values to a timezone-naive normalized Pandas date/datetime representation.
- Do not infer locale-specific formats such as `DD/MM/YYYY`.
- Do not replace invalid dates with missing values and continue silently.

## 11. Context-note validation requirements

## 11.1 `note_id`

- Required and non-blank.
- Unique after safe string normalization.
- Preserved as a string.

## 11.2 `date`

- Strict `YYYY-MM-DD` parsing.
- Timezone-naive normalized representation.
- No semantic expansion into an effective interval during Phase 2.

## 11.3 `applies_to`

- Required and non-blank.
- Preserve values such as `All Routes` and explicit route names.
- Trim outer whitespace in the working copy.
- Do not yet decide whether the named route exists in shipment data; cross-dataset evidence semantics belong to Phase 6 or 7.

## 11.4 `note`

- Required and non-blank.
- Preserve wording and punctuation.
- Do not run an LLM, summarizer, sentiment model, or rule-based causal parser.

## 12. Normalization and derived fields

Normalization must operate on a copy after blocking validation succeeds.

Append these shipment fields in this order:

```text
route
week_of
tonne_km
```

## 12.1 `route`

```text
route = normalized_origin + "-" + normalized_destination
```

Requirements:

- Directional route identity must be preserved.
- Do not alphabetically reorder cities.
- Do not derive or change `route_type` from distance.

## 12.2 `week_of`

For every shipment date, calculate the Monday of that Monday-Sunday week.

Examples:

| Shipment date | Day | Expected `week_of` |
|---|---|---|
| 2024-01-01 | Monday | 2024-01-01 |
| 2024-01-03 | Wednesday | 2024-01-01 |
| 2024-01-07 | Sunday | 2024-01-01 |
| 2024-01-08 | Monday | 2024-01-08 |

Requirements:

- Use calendar arithmetic based on weekday.
- Do not use a week convention that begins on Sunday.
- Store `week_of` as a date-like value, not a formatted descriptive string.

## 12.3 `tonne_km`

```text
tonne_km = quantity_tonnes * distance_km
```

Requirements:

- Preserve full floating-point precision.
- Confirm the result is finite and strictly positive.
- Do not calculate `freight_cost_inr / tonne_km` yet.
- Do not aggregate shipments in Phase 2.

## 12.4 Ordering

The normalized shipment frame must preserve original source row order. Deterministic analytical sorting belongs to the phase that performs aggregation.

## 13. Validation CLI

Create a human-facing validation command runnable from the documented project location, for example:

```bash
cd backend
python -m scripts.validate_inputs
```

The command must:

- Load settings.
- Validate all required input files.
- Print one concise summary per dataset.
- Print validation issues in a stable order.
- Exit with code `0` when all blocking validation succeeds.
- Exit with code `1` for data validation errors.
- Exit with code `2` for missing, unreadable, empty, or undecodable files.
- Avoid printing every source row.
- Avoid writing normalized data to disk during this phase.

Example successful output shape:

```text
FreightGuard input validation
shipment_records.csv: valid (2940 rows)
context_notes.csv: valid (10 rows)
sample_output_format_v2.csv: header valid (8 columns, 1 body-format warning)
Result: PASS
```

Exact wording may follow the project's logging style, but status and counts must remain clear.

## 14. Required supplied-data verification

When run against the supplied files, the implementation should establish at least:

```text
Shipment rows: 2940
Shipment columns before derivation: 10
Context-note rows: 10
Context-note columns: 4
Output-contract columns: 8
Unique shipment IDs: 2940
Missing shipment values: 0
Non-positive required numeric values: 0
Shipment date range: 2024-01-01 through 2025-12-28
Normalized directional routes: 7
Distinct Monday week_of values: 104
```

These values may be asserted in an integration regression test for the supplied challenge files. Unit tests must still use small independent fixtures and must not rely exclusively on these known counts.

## 15. Unit-test requirements

Use small temporary files or committed test fixtures. Do not modify the real supplied data.

## 15.1 Shipment structural tests

Test:

- Valid minimal shipment CSV loads.
- Missing required column fails.
- Unexpected column fails.
- Duplicate header fails.
- Empty file fails.
- Header-only file behavior is explicit and tested.

Recommended decision: a header-only shipment file is structurally valid but operationally empty and should fail with a clear `empty_dataset` or equivalent error.

## 15.2 Shipment identifier tests

Test:

- Duplicate shipment IDs fail.
- Blank shipment ID fails.
- Whitespace-only shipment ID fails.
- IDs remain strings.

## 15.3 Shipment categorical tests

Test:

- `Short`, `Medium`, and `Long` pass.
- `short`, `LONG`, unknown values, blanks, and nulls fail.
- Blank origin or destination fails.
- Blank material or transporter fails.

## 15.4 Shipment numeric tests

For each numeric field, test:

- Valid integer and decimal values pass where appropriate.
- Zero fails.
- Negative value fails.
- Non-numeric value fails.
- NaN fails.
- Positive and negative infinity fail.
- Values are not rounded during ingestion.

## 15.5 Date tests

Test:

- Valid ISO date passes.
- Impossible date fails.
- `DD/MM/YYYY` fails.
- Timestamp text fails unless the project explicitly documents acceptance.
- Leap-day handling is correct.

## 15.6 Normalization tests

Test:

- Directional route generation.
- Outer whitespace trimming in working copies.
- Monday date remains the same Monday.
- Tuesday through Sunday map to the preceding Monday.
- `tonne_km` uses multiplication with full precision.
- Source-row ordering remains unchanged.
- Raw fixture bytes remain unchanged after loading.

## 15.7 Context-note tests

Test:

- Valid note file loads.
- Duplicate `note_id` fails.
- Blank note fails.
- Invalid date fails.
- `All Routes` remains unchanged.
- Original note wording and punctuation are preserved.

## 15.8 Output-contract tests

Test:

- Exact required header passes.
- Wrong order fails.
- Missing output column fails.
- Extra output column fails.
- Duplicate output column fails.
- Unquoted commas in illustrative body rows generate a warning without changing the authoritative valid header.

## 15.9 Error-report tests

Test:

- Multiple independent issues are collected.
- Issues are displayed in deterministic order.
- Exceptions contain structured issues.
- Error messages do not contain complete raw rows.
- CLI exit codes match the documented contract.

## 16. Integration-test requirements

Create an integration test for the actual supplied inputs that:

- Loads the bundle using application settings or an isolated settings instance.
- Confirms shipment and note counts.
- Confirms exact canonical source columns.
- Confirms derived columns exist.
- Confirms `week_of` values are Mondays.
- Confirms every `tonne_km` value is finite and positive.
- Confirms seven directional routes and 104 distinct `week_of` values.
- Confirms the output header contract.
- Confirms original file hashes are unchanged before and after loading.

Do not make this the only test coverage. It is a regression test in addition to focused unit tests.

## 17. Logging requirements

Use the logging setup established in Phase 1.

Log at an appropriate level:

- Input filename
- Dataset identifier
- Validation start and completion
- Row and column counts
- Number of warnings and errors

Do not log:

- Complete shipment rows
- Full context-note bodies by default
- Environment secrets
- Entire DataFrames

## 18. Documentation updates

Update only relevant documentation:

### README

Add:

- Phase 2 status
- Pandas installation through requirements
- Input file locations
- Validation command
- Expected successful validation summary
- Explanation that Phase 2 validates and normalizes but does not perform anomaly detection

### `docs/DECISIONS.md`

Add decisions such as:

```text
ADR-006: Reject malformed source values instead of silently coercing them
ADR-007: Preserve raw inputs and normalize only in memory
ADR-008: Treat the sample output header as authoritative
ADR-009: Use strict ISO dates and Monday-based week_of derivation
ADR-010: Centralize CSV access through the ingestion service
```

### Implementation checklist

Mark Phase 2 complete only after all acceptance criteria pass. Do not mark Phase 3 started.

## 19. Quality and maintainability requirements

- Use type hints for public functions.
- Prefer pure validation functions that are easy to test.
- Keep file I/O separate from validation logic.
- Keep normalization separate from aggregation.
- Avoid chained Pandas assignments that can mutate views unexpectedly.
- Avoid `inplace=True` when a returned copy is clearer.
- Use named constants for column contracts and allowed route types.
- Do not scatter filenames or expected columns throughout the codebase.
- Do not silently skip malformed rows.
- Do not modify source files.
- Do not duplicate CSV-loading logic in scripts or API routes.
- Avoid a generic `utils.py` dumping ground.
- Preserve existing application behaviour and Phase 1 tests.

## 20. Explicit non-goals for Phase 2

Codex must not implement:

- Weekly route aggregation
- Cost-per-tonne-kilometre calculation
- Own-history rolling averages
- Similar-route peer averages
- Anomaly thresholds or candidate flags
- Submission CSV generation
- Context-note semantic interpretation
- Effective note-date ranges
- Embeddings or vector databases
- Evidence matching
- LLM integration
- Explanation generation
- Token or model-cost tracking
- New API analysis endpoints
- File-upload endpoints
- Database persistence
- React initialization
- Docker setup
- Natural-language Q&A

Derived `tonne_km` is allowed. Dividing freight cost by `tonne_km` or aggregating it belongs to Phase 3.

## 21. Required verification commands

Codex must adapt commands to the actual established repository and report the exact commands that succeeded.

### Install updated dependencies

```bash
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-dev.txt
```

### Run all backend tests

```bash
python -m pytest backend/tests -q
```

### Run Phase 2 tests with coverage

```bash
python -m pytest backend/tests/unit backend/tests/integration -q --cov=backend/app/services/ingestion
```

Adjust the coverage import path to the repository's actual package layout without weakening the tested scope.

### Lint

```bash
python -m ruff check backend
```

### Validate supplied inputs

```bash
cd backend
python -m scripts.validate_inputs
```

For Windows PowerShell:

```powershell
Set-Location backend
python -m scripts.validate_inputs
```

No command should be left waiting indefinitely.

## 22. Acceptance criteria

Phase 2 is complete only when all conditions below are satisfied:

- [x] Pandas is added using the project's existing dependency strategy.
- [x] Canonical input and output contracts are centralized.
- [x] Shipment loader validates file, header, values, and identifiers.
- [x] Context-note loader validates file, header, values, and identifiers.
- [x] Output-contract loader validates the exact eight-column header.
- [x] Supplied sample body-format inconsistency is handled as documented without rewriting the file.
- [x] Missing, empty, unreadable, and malformed files produce clear structured errors.
- [x] Multiple validation issues can be reported together.
- [x] Valid shipments receive `route`, `week_of`, and `tonne_km` fields.
- [x] Route direction is preserved.
- [x] Every `week_of` value is a Monday.
- [x] Every valid `tonne_km` value is finite and positive.
- [x] Original source rows and files are not modified.
- [x] `load_input_bundle` is the public ingestion entry point.
- [x] Validation CLI returns documented exit codes.
- [x] Unit tests cover structural, identifier, text, numeric, date, normalization, and error cases.
- [x] Integration test validates the supplied challenge files.
- [x] Supplied shipment data produces 2,940 normalized records.
- [x] Supplied context data produces 10 validated notes.
- [x] Supplied data produces seven directional routes and 104 Monday weeks.
- [x] Existing Phase 1 tests continue to pass.
- [x] Ruff reports no errors.
- [x] README and architectural decisions are updated.
- [x] No Phase 3 or later logic is implemented.
- [x] Codex reports changed files, commands, results, limitations, and a commit message.
- [x] Codex stops after Phase 2.

## 23. Suggested Phase 2 commit message

```text
feat: add strict input validation and normalization
```

## 24. Copy-paste instruction for Codex

```text
Read AGENTS.md, docs/PROJECT_SPEC.md, docs/IMPLEMENTATION_PLAN.md,
docs/DECISIONS.md, FREIGHTGUARD_MASTER_IMPLEMENTATION_ROADMAP.md, and
FREIGHTGUARD_PHASE_2_DATA_INGESTION_VALIDATION_PLAN.md completely before
editing.

Inspect the existing repository and confirm that Phase 1 is complete. Preserve
all unrelated existing work and follow the project's established package and
dependency conventions.

Implement Phase 2 only according to
FREIGHTGUARD_PHASE_2_DATA_INGESTION_VALIDATION_PLAN.md.

Build strict loaders, structured validation errors, normalized in-memory
working copies, derived route/week_of/tonne_km fields, the authoritative output
header contract, and the local validation command. Use the supplied input files
without modifying their bytes.

The supplied sample output contains illustrative natural-language rows with
commas that may not be consistently quoted. Treat its first record as the
authoritative eight-column header contract, surface malformed body rows as a
non-blocking diagnostic, and do not rewrite the supplied file.

Do not implement weekly aggregation, cost-per-tonne-km calculation, rolling
baselines, peer baselines, anomaly detection, evidence retrieval, LLM features,
new analysis API endpoints, React, Docker, or database persistence.

Add focused unit tests and a supplied-data integration test. Run the entire
existing backend test suite, Phase 2 tests, Ruff, and the validation CLI with
sensible timeouts. Do not leave a process waiting indefinitely.

When finished, report:

1. What was implemented
2. Every file created or modified
3. Important engineering decisions and deviations from this plan
4. Commands executed and their exact results
5. Supplied-data validation counts and warnings
6. Exact manual verification steps
7. Any limitations or blockers
8. A concise Git commit message

Update the Phase 2 checklist, then stop. Do not begin Phase 3.
```
