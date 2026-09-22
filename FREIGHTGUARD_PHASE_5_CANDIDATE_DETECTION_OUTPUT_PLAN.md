# FreightGuard AI - Phase 5 Candidate Detection and Output Contract Plan

## 1. Purpose of this document

This document is the complete implementation contract for Phase 5 of FreightGuard AI. Give it to Codex after Phases 1 through 4 have been completed, tested, and committed.

Phase 5 converts Phase 4 baseline-enriched weekly metrics into deterministic percentage comparisons, applies the configurable candidate-anomaly rule, and writes the first CSV matching the challenge's exact eight-column output contract.

At this phase, contextual notes have not yet been semantically evaluated. Therefore, every detected candidate remains flagged and has a blank `matched_note_id`. The Phase 5 CSV is a preliminary candidate output, not the final evidence-reviewed submission.

Phase 5 does not retrieve notes, decide whether a rise is justified, generate AI explanations, or clear any candidate.

## 2. Phase objective

Build a deterministic candidate-detection and export layer that:

- Consumes the canonical Phase 4 baseline-enriched metrics.
- Calculates full-precision percentage deviations from own history and peers.
- Applies a configurable and auditable anomaly rule.
- Handles unavailable baselines without converting them to zero.
- Retains rule-component booleans for inspection and testing.
- Selects candidate rows only for the preliminary output.
- Formats display fields exactly and consistently.
- Writes an RFC-compliant CSV with the required columns and order.
- Validates the written CSV by reading it back.
- Produces deterministic bytes for identical input and configuration.
- Provides a CLI for generating and inspecting the candidate output.

After Phase 5, Phase 6 should be able to compile context notes without changing any canonical calculations or candidate decisions.

## 3. Preconditions

Before editing, Codex must verify:

- All Phase 1 through Phase 4 tests pass.
- The Phase 2 input bundle loads successfully.
- The Phase 3 weekly metrics service reports 728 supplied-data rows.
- The Phase 4 baseline service preserves 728 rows and passes leakage/self-exclusion tests.
- The configured anomaly threshold exists and defaults to `20.0` percent.
- The configured output directory exists and generated files remain ignored by Git.
- The Phase 2 output-header contract is available centrally.
- Original challenge input files remain unchanged.
- The Git working tree is inspected and unrelated changes are preserved.

If equivalent interfaces use different names, adapt to the existing architecture without rewriting correct earlier-phase code. Report material deviations.

## 4. Input contract

The comparison service must consume the Phase 4 canonical DataFrame with these columns:

```text
route
route_type
week_of
shipment_count
total_freight_cost_inr
total_quantity_tonnes
total_tonne_km
cost_per_tonne_km
own_history_avg_cost_per_tonne_km
history_weeks_used
similar_routes_avg_cost_per_tonne_km
peer_routes_used
```

Required preconditions:

- The DataFrame is not empty.
- Required columns exist exactly once.
- Group keys remain unique.
- `cost_per_tonne_km` is numeric, finite, and strictly positive.
- Available baselines are numeric, finite, and strictly positive.
- Missing baseline values are consistent with zero audit counts.
- Phase 3 and Phase 4 values remain unrounded.

The service must not read raw CSV files or recompute weekly cost/baselines.

## 5. Percentage comparison contract

## 5.1 Own-history deviation

For every row with an available own-history baseline:

```text
vs_own_history_pct =
    (
        cost_per_tonne_km
        / own_history_avg_cost_per_tonne_km
        - 1
    ) * 100
```

Examples:

- Current `4.0`, baseline `3.0` gives `+33.333...%`.
- Current `3.0`, baseline `4.0` gives `-25.0%`.
- Current equals baseline gives `0.0%`.

When own history is unavailable:

- `vs_own_history_pct` remains missing.
- Do not replace it with zero.
- The row cannot be classified as rising under the Phase 5 rule.

## 5.2 Similar-route deviation

For every row with an available peer baseline:

```text
vs_similar_routes_pct =
    (
        cost_per_tonne_km
        / similar_routes_avg_cost_per_tonne_km
        - 1
    ) * 100
```

When the peer baseline is unavailable:

- `vs_similar_routes_pct` remains missing.
- Do not replace it with zero.
- The peer threshold component evaluates to false.
- The route may still become a candidate through the own-history threshold when history is available and rising.

## 5.3 Precision rules

- Calculate comparisons from full-precision canonical values.
- Do not round before threshold evaluation.
- Retain full-precision numeric comparison columns internally.
- Round only when constructing user-facing CSV fields.
- Do not store `+35.5%` strings in the analytical DataFrame.

## 6. Candidate anomaly rule

## 6.1 Configurable threshold

Use the Phase 1 setting:

```text
ANOMALY_THRESHOLD_PERCENT=20.0
```

Requirements:

- The threshold must be passed explicitly into the pure candidate function or obtained once by a thin orchestration layer.
- Do not access global settings deep inside vectorized rule logic.
- Threshold must be numeric, finite, and non-negative.
- Use the same threshold for own-history and peer comparisons during Phase 5.
- Do not scatter the literal `20.0` throughout the code.

## 6.2 Rule components

Create these internal boolean fields:

```text
is_rising
own_threshold_breached
peer_threshold_breached
candidate_anomaly
```

Definitions:

```text
is_rising =
    own history is available
    AND vs_own_history_pct > 0

own_threshold_breached =
    own history is available
    AND vs_own_history_pct >= threshold

peer_threshold_breached =
    peer baseline is available
    AND vs_similar_routes_pct >= threshold

candidate_anomaly =
    is_rising
    AND
    (
        own_threshold_breached
        OR peer_threshold_breached
    )
```

## 6.3 Boundary semantics

- A value exactly equal to the threshold counts as a breach.
- Rising is strict: `vs_own_history_pct > 0`.
- Exactly `0%` above history is not rising.
- A negative own-history deviation cannot become a candidate solely because the peer deviation is high.
- Missing own history means `is_rising = False` and `candidate_anomaly = False`.
- Missing peers do not prevent an own-history-triggered candidate.
- Missing numerical comparisons must not propagate into nullable/ambiguous boolean decisions; rule columns must contain ordinary `True` or `False` only.

## 6.4 Why positive own-history movement is required

The challenge asks for routes where cost is rising and looks unusual compared with history or similar routes. Phase 5 operationalizes “rising” as being above the route group's own prior-history baseline.

Document this decision because the challenge specifies exact baselines but does not prescribe an exact flagging threshold or Boolean rule.

## 7. Demonstration rule matrix

With threshold `20.0`:

| Own deviation | Peer deviation | Rising? | Threshold breach | Candidate? | Reason |
|---:|---:|---|---|---|---|
| +35% | +21% | Yes | Own and peer | Yes | Clearly elevated |
| +9% | +24% | Yes | Peer | Yes | Rising and peer outlier |
| +25% | -5% | Yes | Own | Yes | Own-history outlier |
| -5% | +40% | No | Peer only | No | Not rising versus own history |
| 0% | +30% | No | Peer only | No | Strictly not rising |
| +20% | +1% | Yes | Own equality | Yes | Threshold is inclusive |
| +1% | +20% | Yes | Peer equality | Yes | Threshold is inclusive |
| Missing | +50% | No | Peer only | No | Rising cannot be established |
| +25% | Missing | Yes | Own | Yes | Peer absence does not block own trigger |

Add unit tests for every row in this matrix.

## 8. Canonical internal comparison schema

Return a new DataFrame containing all Phase 4 columns plus:

```text
vs_own_history_pct
vs_similar_routes_pct
is_rising
own_threshold_breached
peer_threshold_breached
candidate_anomaly
```

Append them in that order.

Requirements:

- Preserve all Phase 4 rows and values.
- Percentage columns remain numeric and unrounded.
- Missing percentages remain numeric missing values.
- Rule-component columns are non-null booleans.
- Candidate decision is not stored as a display string.
- Input DataFrame is not mutated.
- Canonical sort order remains `route`, `route_type`, `week_of` ascending.

## 9. Preliminary candidate output contract

## 9.1 Rows included

Include only rows where:

```text
candidate_anomaly == True
```

Do not include every one of the 728 route-weeks in the candidate CSV.

Candidates remain present in later final output even when contextual evidence ultimately clears them. Later phases will update verdict, note ID, and reason rather than deleting justified candidate rows.

## 9.2 Exact columns and order

The CSV must contain exactly:

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

Use the Phase 2 authoritative output-header contract rather than duplicating a competing definition.

## 9.3 Field formatting

### `route`

- Use the canonical directional route string.

### `week_of`

- Serialize as ISO date `YYYY-MM-DD`.
- No timestamp or timezone suffix.

### `cost_per_tonne_km`

- Output as a numeric value rounded to two decimal places for display.
- Keep the internal canonical analytical value unrounded.

### `vs_own_history`

Format using one decimal place and an explicit sign:

```text
+35.5% vs this route's past average
```

### `vs_similar_routes`

Format using one decimal place and an explicit sign:

```text
+21.0% vs similar-length routes this week
```

All candidate rows must have an own-history comparison. A peer comparison can theoretically be unavailable. If a candidate was triggered only through own history and has no peer baseline, use a clear stable phrase such as:

```text
Not available: no other same-type routes this week
```

Do not represent an unavailable peer comparison as `+0.0%`.

### `flagged`

During Phase 5:

```text
Yes
```

Every candidate remains flagged because contextual justification has not yet been evaluated.

### `matched_note_id`

During Phase 5:

```text
blank string
```

Do not place `None`, `NaN`, `null`, or an invented note ID in the CSV cell.

### `reason`

Use one deterministic preliminary reason for all Phase 5 candidates:

```text
Context review pending. Cost rise is currently flagged for review.
```

Do not claim that no matching note exists, because note matching has not happened yet.

## 9.4 Preliminary filename

Use a filename that cannot be confused with the final evidence-reviewed deliverable, for example:

```text
backend/data/output/candidate_anomalies.csv
```

Do not name it `final_submission.csv` during Phase 5.

## 10. Required project structure changes

Extend the existing codebase without moving correct earlier-phase modules:

```text
backend/
├── app/
│   └── services/
│       ├── analytics/
│       │   ├── comparisons.py
│       │   └── candidates.py
│       └── reporting/
│           ├── __init__.py
│           └── candidate_csv.py
├── scripts/
│   └── generate_candidate_output.py
└── tests/
    ├── unit/
    │   ├── test_comparisons.py
    │   ├── test_candidate_detection.py
    │   └── test_candidate_csv.py
    └── integration/
        └── test_candidate_output_supplied_data.py
```

Responsibilities:

- `comparisons.py`: calculate numeric percentage deviations.
- `candidates.py`: apply configurable Boolean rule components.
- `reporting/candidate_csv.py`: map candidates to the exact display contract, write CSV, and validate round-trip structure.
- `generate_candidate_output.py`: orchestrate Phases 2 through 5.
- Existing analytics contracts: centralize Phase 5 column names.
- Existing analytics errors: reuse or extend focused domain exceptions.

Equivalent names are acceptable when consistent with the implemented repository. Do not combine the full pipeline, formatting, and file writing into one oversized function.

## 11. Public interfaces

Provide independently testable functions equivalent to:

```python
def add_percentage_comparisons(
    baseline_metrics: pandas.DataFrame,
) -> pandas.DataFrame:
    ...

def detect_candidate_anomalies(
    comparison_metrics: pandas.DataFrame,
    threshold_percent: float,
) -> pandas.DataFrame:
    ...

def build_candidate_output(
    candidate_metrics: pandas.DataFrame,
    output_columns: tuple[str, ...],
) -> pandas.DataFrame:
    ...

def write_candidate_csv(
    output: pandas.DataFrame,
    destination: pathlib.Path,
) -> pathlib.Path:
    ...
```

Requirements:

- Comparison and detection functions are pure or nearly pure.
- Formatting is separate from canonical calculations.
- File writing is separate from DataFrame construction.
- No function reads raw challenge CSV files directly.
- No context-note logic appears in comparison or detection functions.
- Input DataFrames are not mutated.

## 12. Required calculation procedure

Implement the Phase 5 flow clearly:

1. Validate Phase 4 required columns and baseline consistency.
2. Create a working copy.
3. Calculate full-precision own-history deviation where available.
4. Calculate full-precision peer deviation where available.
5. Validate threshold configuration.
6. Calculate `is_rising`.
7. Calculate own-threshold breach.
8. Calculate peer-threshold breach.
9. Calculate `candidate_anomaly`.
10. Confirm Boolean columns contain no missing values.
11. Preserve canonical sort order and reset index.
12. Filter candidate rows for the preliminary output.
13. Map candidate rows into the exact eight-column display contract.
14. Sort output by `route` and `week_of` ascending.
15. Write RFC-compliant CSV.
16. Read the CSV back and validate its header, field counts, row count, and order.
17. Return or report the generated path and summary.

## 13. CSV writing requirements

Use the Python standard-library `csv` module or Pandas with explicit RFC-safe options.

Requirements:

- UTF-8 encoding.
- Header included exactly once.
- No DataFrame index column.
- Exact eight-column order.
- Stable `\n` line endings where practical for byte reproducibility across repeated local runs.
- Minimal standards-compliant quoting.
- Commas, quotes, and newlines inside a future `reason` must be safely escaped.
- Blank `matched_note_id` must serialize as an empty field.
- Parent output directory may be created if it does not exist.
- Write through a temporary file and atomically replace the destination where practical, so a failed run does not leave a partial CSV.
- Do not overwrite any supplied input file.

## 14. Round-trip output validation

After writing, validate the generated file using an independent read path where practical.

Verify:

- Header exactly matches the authoritative output contract.
- Every data record contains exactly eight logical fields.
- Row count equals candidate count.
- No accidental index column exists.
- `route` and `week_of` ordering is deterministic.
- Every `flagged` value equals `Yes` during Phase 5.
- Every `matched_note_id` cell is blank.
- Every reason equals the preliminary deterministic reason.
- `cost_per_tonne_km` cells are parseable numeric values.
- `week_of` cells match ISO date format.
- Comparison fields are non-empty.

Include a test reason containing a comma and quotes to prove the writer round-trips it correctly even though the Phase 5 default reason is simple.

## 15. Determinism requirements

- Full-precision candidate decisions must not depend on display rounding.
- Shuffling Phase 4 input must yield identical canonical comparison output after sorting.
- Repeated calls with the same threshold must yield identical candidate rows.
- Repeated file generation must produce identical bytes for the same environment and inputs.
- Calculate and print SHA-256 for the generated candidate CSV.
- Do not include timestamps, random IDs, machine paths, or non-deterministic metadata in the CSV.

The formal three-run reproducibility harness remains Phase 9 work, but Phase 5 must already be deterministic by construction.

## 16. Candidate pipeline CLI

Create:

```bash
cd backend
python -m scripts.generate_candidate_output
```

The command must:

1. Load settings and Phase 2 inputs once.
2. Run Phase 3 weekly analytics.
3. Run Phase 4 baselines.
4. Calculate Phase 5 comparisons and candidates.
5. Build the exact preliminary output.
6. Write `candidate_anomalies.csv` under the configured output directory.
7. Validate the file after writing.
8. Print a concise deterministic summary.

Suggested output:

```text
FreightGuard candidate detection
Weekly route groups evaluated: 728
Threshold: 20.0%
Candidates detected: 19
Triggered by own history: 6
Triggered by peers: 18
Triggered by both: 5
Output rows: 19
Output contract: PASS
Output: backend/data/output/candidate_anomalies.csv
SHA-256: <hash>
```

The exact trigger counts must be calculated by code and asserted only after verifying them against the implemented Boolean definitions. Do not hardcode CLI display counts.

The command must exit non-zero on ingestion, analytics, formatting, or output-validation failure. Expected domain errors should be concise.

## 17. Unit-test requirements

Use small Phase 4-shaped DataFrames for focused tests.

## 17.1 Percentage calculation tests

Test:

- Positive own-history deviation.
- Negative own-history deviation.
- Exactly zero deviation.
- Positive and negative peer deviations.
- Missing own baseline produces missing own percentage.
- Missing peer baseline produces missing peer percentage.
- Full precision is retained.
- Input DataFrame is unchanged.

## 17.2 Rule-matrix tests

Implement every case in Section 7, including:

- Both thresholds exceeded.
- Peer-only breach with positive own movement.
- Own-only breach.
- High peer deviation with declining own history.
- Zero own movement.
- Threshold equality.
- Missing own history.
- Missing peers.

## 17.3 Threshold-validation tests

Test rejection of:

- Negative threshold
- NaN threshold
- Positive infinity
- Negative infinity
- Non-numeric threshold

Test valid behaviour for:

- Zero threshold
- Decimal threshold
- Default `20.0`

## 17.4 Rounding-separation tests

Create values where:

- Full precision is just below `20.0`, but one-decimal display rounds to `20.0%`.
- Full precision is exactly `20.0`.
- Full precision is just above `20.0`.

Assert that candidate decisions use full precision, not formatted strings.

## 17.5 Output-format tests

Test:

- Exact header and column order.
- Candidate rows only.
- ISO date output.
- Two-decimal cost display.
- One-decimal signed percentage display.
- Blank matched note field.
- `flagged = Yes`.
- Preliminary reason exact wording.
- No DataFrame index column.
- Correct deterministic row ordering.
- Header-only output when there are zero candidates.

## 17.6 CSV quoting tests

Test round trips for reasons containing:

- Comma
- Double quote
- Newline

Every logical row must still contain eight fields when parsed by a compliant CSV reader.

## 17.7 Determinism and immutability tests

Test:

- Shuffled input yields identical canonical output.
- Repeated calls yield equal DataFrames.
- Two writes produce identical bytes and SHA-256.
- Phase 4 input is unchanged.

## 18. Supplied-data integration and regression tests

Compose the complete Phase 2 through Phase 5 pipeline with the default threshold `20.0`.

Expected summary:

```text
Weekly route groups evaluated: 728
Candidate anomalies: 19
Preliminary flagged Yes: 19
Preliminary matched_note_id populated: 0
Output rows: 19
Output columns: 8
```

Expected candidate keys and one-decimal display values:

| Route | Week of | Cost/tonne-km | Own history | Similar routes |
|---|---|---:|---:|---:|
| Ahmedabad-Mumbai | 2025-01-20 | 3.29 | +29.5% | +22.5% |
| Chennai-Bangalore | 2025-02-24 | 3.58 | +31.5% | +38.7% |
| Chennai-Bangalore | 2025-03-03 | 3.48 | +22.8% | +32.0% |
| Chennai-Bangalore | 2025-03-10 | 3.57 | +22.1% | +33.8% |
| Chennai-Bangalore | 2025-03-17 | 3.47 | +13.7% | +33.5% |
| Delhi-Jaipur | 2024-11-11 | 4.17 | +35.5% | +21.0% |
| Delhi-Jaipur | 2024-11-18 | 4.09 | +27.6% | +19.7% |
| Mumbai-Pune | 2025-06-23 | 3.76 | +6.2% | +20.6% |
| Mumbai-Pune | 2025-09-15 | 3.98 | +9.2% | +23.6% |
| Mumbai-Pune | 2025-10-06 | 3.94 | +5.4% | +22.9% |
| Mumbai-Pune | 2025-10-20 | 4.10 | +7.7% | +24.8% |
| Mumbai-Pune | 2025-10-27 | 4.07 | +5.5% | +28.3% |
| Mumbai-Pune | 2025-11-03 | 4.20 | +7.4% | +24.1% |
| Mumbai-Pune | 2025-11-17 | 4.32 | +8.9% | +31.6% |
| Mumbai-Pune | 2025-11-24 | 4.16 | +3.0% | +23.0% |
| Mumbai-Pune | 2025-12-01 | 4.39 | +7.7% | +37.4% |
| Mumbai-Pune | 2025-12-08 | 4.43 | +7.2% | +38.8% |
| Mumbai-Pune | 2025-12-15 | 4.39 | +4.4% | +35.5% |
| Mumbai-Pune | 2025-12-22 | 4.49 | +5.7% | +38.9% |

Regression tests must compare candidate keys exactly. Numeric internal comparisons should be asserted before formatting, using appropriate floating-point tolerance.

## 19. Analytical invariants

Before output generation, verify:

## 19.1 Row preservation

Comparison calculation preserves all Phase 4 rows.

## 19.2 Percentage availability

- Own percentage is missing exactly when own baseline is missing.
- Peer percentage is missing exactly when peer baseline is missing.

## 19.3 Boolean completeness

Rule-component and candidate columns contain no missing values.

## 19.4 Candidate subset

Every candidate row satisfies:

```text
vs_own_history_pct > 0
```

and at least one threshold component is true.

## 19.5 Non-candidate complement

No non-candidate row satisfies the complete configured candidate rule.

## 19.6 Key uniqueness

Candidate keys remain unique.

## 19.7 Output reconciliation

```text
number of output rows == number of candidate_anomaly True rows
```

If an invariant fails, raise a focused analytics or reporting error rather than writing a misleading file.

## 20. Error handling

Reuse or extend the existing domain hierarchy cleanly, for example:

```text
AnalyticsError
├── AnalyticsInputError
└── CandidateDetectionError

ReportingError
└── OutputContractError
```

Raise clear errors for:

- Missing Phase 4 columns
- Invalid or inconsistent baselines
- Invalid threshold
- Non-finite percentage result
- Nullable rule Boolean
- Candidate invariant failure
- Output-header mismatch
- Output directory failure
- Partial or failed write
- Round-trip validation failure

Do not silently omit failed candidate rows or continue after a broken output contract.

## 21. Performance requirements

- Use vectorized Pandas arithmetic and Boolean masks.
- Avoid row-wise `apply` for candidate calculations when vectorized expressions are clear.
- Formatting 19 candidate rows may use straightforward mapping functions.
- Load source data once per CLI run.
- Do not introduce multiprocessing, caching, a database, or distributed computing.
- The Phase 2 through Phase 5 pipeline should complete comfortably within ordinary local test timeouts.

## 22. Logging requirements

Log concise operational information:

- Threshold used
- Weekly rows evaluated
- Count of own and peer threshold breaches
- Candidate count
- Output path
- Output row count
- Contract-validation status
- SHA-256 hash

Do not log:

- Entire DataFrames
- Context-note bodies
- Secrets
- Every non-candidate row

## 23. Documentation updates

### README

Add:

- Phase 5 status
- Exact deviation formulas
- Exact default candidate rule
- Explanation that the 20% threshold is configurable because the brief does not specify one
- Missing-baseline behaviour
- Candidate generation command
- Preliminary output location
- Warning that Phase 5 has not evaluated context notes yet
- Expected supplied-data candidate count

### `docs/DECISIONS.md`

Add decisions such as:

```text
ADR-021: Require positive own-history movement before candidate flagging
ADR-022: Use inclusive configurable thresholds on own or peer deviation
ADR-023: Apply thresholds to full-precision values before display rounding
ADR-024: Export candidate rows only using the exact eight-column contract
ADR-025: Keep preliminary candidates flagged until evidence evaluation
ADR-026: Validate generated CSV through an independent round trip
```

### Implementation checklist

Mark Phase 5 complete only after all acceptance criteria pass. Do not mark Phase 6 started.

## 24. Quality and maintainability requirements

- Use type hints for public functions.
- Separate calculations, rules, formatting, and file writing.
- Keep column names centralized.
- Keep threshold injected into pure logic.
- Preserve full precision internally.
- Preserve earlier canonical columns and values.
- Avoid chained assignments and ambiguous views.
- Do not duplicate Phase 2 loading, Phase 3 aggregation, or Phase 4 baselines.
- Do not derive canonical decisions from formatted strings.
- Use an RFC-compliant CSV writer.
- Keep generated outputs out of version control unless explicitly required for submission.
- Preserve all earlier tests and source-file hashes.

## 25. Explicit non-goals for Phase 5

Codex must not implement:

- Context-note semantic normalization
- Note effective-date extraction
- Note route matching
- Vector embeddings or vector databases
- RAG retrieval
- Evidence Gate verdicts
- `No (justified)` decisions
- Populated `matched_note_id` values
- Claims that no supporting note exists
- AI-generated explanations
- LLM provider integration
- Token or model-cost logging
- Formal three-run reproducibility report
- New FastAPI analysis endpoints
- Database persistence
- React frontend or charts
- Docker configuration
- Natural-language Q&A

Phase 5 may write only the preliminary candidate CSV. Final evidence-reviewed output belongs to later phases.

## 26. Required verification commands

Codex must adapt these commands to the established repository and report exact results.

### Complete backend tests

```bash
python -m pytest backend/tests -q
```

### Focused Phase 5 tests with coverage

```bash
python -m pytest \
  backend/tests/unit/test_comparisons.py \
  backend/tests/unit/test_candidate_detection.py \
  backend/tests/unit/test_candidate_csv.py \
  backend/tests/integration/test_candidate_output_supplied_data.py \
  -q --cov=backend/app/services
```

Windows PowerShell equivalent may be written on one line.

### Lint

```bash
python -m ruff check backend
```

### Run prior inspection commands and generate output

```bash
cd backend
python -m scripts.validate_inputs
python -m scripts.inspect_weekly_metrics
python -m scripts.inspect_baselines
python -m scripts.generate_candidate_output
```

For Windows PowerShell:

```powershell
Set-Location backend
python -m scripts.validate_inputs
python -m scripts.inspect_weekly_metrics
python -m scripts.inspect_baselines
python -m scripts.generate_candidate_output
```

### Inspect generated header

Use a safe read-only command appropriate for the operating system to confirm the exact eight-column header. Do not manually edit the generated file.

No command may be left waiting indefinitely.

## 27. Acceptance criteria

Phase 5 is complete only when every applicable condition passes:

- [x] All Phase 1 through Phase 4 tests still pass.
- [x] Comparison logic consumes Phase 4 metrics rather than recalculating baselines.
- [x] Own-history and peer deviations use the exact formulas.
- [x] Canonical comparison values remain full precision and numeric.
- [x] Missing baselines produce missing percentages, not zero.
- [x] Default threshold comes from configuration and equals 20.0 percent.
- [x] Invalid thresholds fail clearly.
- [x] `is_rising` requires available own history and a strictly positive deviation.
- [x] Own and peer threshold checks are inclusive.
- [x] Candidate rule matches the documented Boolean expression.
- [x] Rule-component columns contain no missing values.
- [x] Thresholds are applied before display rounding.
- [x] Phase 4 rows and values are preserved.
- [x] Input DataFrames are not mutated.
- [x] Candidate keys are unique and deterministically sorted.
- [x] Preliminary output contains candidate rows only.
- [x] Output has exactly eight columns in the required order.
- [x] Output dates use `YYYY-MM-DD`.
- [x] Display cost uses two decimal places.
- [x] Comparison text uses one decimal place and explicit signs.
- [x] Every Phase 5 `flagged` value is `Yes`.
- [x] Every Phase 5 `matched_note_id` is blank.
- [x] Preliminary reason does not claim evidence was searched.
- [x] CSV commas, quotes, and newlines round-trip correctly.
- [x] No index column is exported.
- [x] Written CSV passes independent contract validation.
- [x] Two identical runs produce identical bytes and SHA-256.
- [x] Default supplied-data run evaluates 728 rows and detects exactly 19 candidates.
- [x] Candidate keys exactly match the 19-row regression set.
- [x] Generated file is named as preliminary candidate output, not final submission.
- [x] README and architecture decisions are updated.
- [x] Ruff reports no errors.
- [x] No Phase 6 or later functionality is implemented.
- [x] Codex reports files, decisions, commands, counts, hash, limitations, and commit message.
- [x] Codex stops after Phase 5.

## 28. Suggested Phase 5 commit message

```text
feat: detect cost anomalies and export candidate CSV
```

## 29. Copy-paste instruction for Codex

```text
Read AGENTS.md, docs/PROJECT_SPEC.md, docs/IMPLEMENTATION_PLAN.md,
docs/DECISIONS.md, FREIGHTGUARD_MASTER_IMPLEMENTATION_ROADMAP.md,
FREIGHTGUARD_PHASE_4_BASELINE_ENGINE_PLAN.md, and
FREIGHTGUARD_PHASE_5_CANDIDATE_DETECTION_OUTPUT_PLAN.md completely before
editing.

Inspect the repository and verify that Phases 1 through 4 are complete.
Preserve unrelated work and adapt to established package conventions without
rewriting correct ingestion, weekly analytics, or baseline logic.

Implement Phase 5 only according to
FREIGHTGUARD_PHASE_5_CANDIDATE_DETECTION_OUTPUT_PLAN.md.

Calculate full-precision own-history and peer percentage deviations from the
Phase 4 baselines. Apply the configured threshold using this exact rule:

candidate = own deviation is available and greater than 0, and either the own
deviation or available peer deviation is greater than or equal to the
configured threshold.

Keep calculations numeric and unrounded. Add explicit Boolean rule components.
Use full-precision values for decisions and round only while constructing the
display output.

Build and write a preliminary candidate CSV with exactly these columns:
route, week_of, cost_per_tonne_km, vs_own_history, vs_similar_routes,
flagged, matched_note_id, reason.

Include candidate rows only. During Phase 5 set flagged to Yes, leave
matched_note_id blank, and use the deterministic reason: Context review
pending. Cost rise is currently flagged for review.

Write an RFC-compliant deterministic CSV named candidate_anomalies.csv under
the configured output directory. Validate it by reading it back and calculate
its SHA-256 hash.

Do not implement context-note parsing, retrieval, Evidence Gate decisions,
justified verdicts, note IDs, AI explanations, LLM integrations, API analysis
endpoints, React, databases, Docker, or the final submission output.

Add focused formula, rule-boundary, rounding-separation, formatting, quoting,
determinism, immutability, and supplied-data regression tests. With the default
20.0 percent threshold, the supplied data must produce exactly 19 candidate
rows matching the plan's regression keys.

Run all backend tests, focused Phase 5 tests with coverage, Ruff, all prior
inspection commands, and candidate generation using sensible timeouts.

When finished, report:

1. What was implemented
2. Every file created or modified
3. Important decisions and deviations from this plan
4. Commands executed and exact results
5. Candidate and trigger counts
6. Output-contract validation result and SHA-256
7. Exact manual verification steps
8. Any limitations or blockers
9. A concise Git commit message

Update the Phase 5 checklist, then stop. Do not begin Phase 6.
```
