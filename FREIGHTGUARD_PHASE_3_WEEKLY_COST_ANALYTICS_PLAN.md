# FreightGuard AI - Phase 3 Weekly Cost Analytics Implementation Plan

## 1. Purpose of this document

This document is the complete implementation contract for Phase 3 of FreightGuard AI. Give it to Codex together with the master implementation roadmap after Phases 1 and 2 have been completed, tested, and committed.

Phase 3 converts validated shipment-level records into deterministic weekly route-level cost metrics. It implements the canonical weighted cost-per-tonne-kilometre calculation and retains enough audit fields to prove every result.

Phase 3 does not calculate historical baselines, peer baselines, deviations, anomaly flags, context matches, evidence verdicts, or AI explanations.

## 2. Phase objective

Build a focused analytics layer that:

- Consumes the validated and normalized shipment DataFrame produced by Phase 2.
- Groups shipments by `route + route_type + week_of`.
- Aggregates every material and transporter inside the appropriate route-week group.
- Calculates weighted weekly cost per tonne-kilometre using the challenge formula.
- Retains numerator, denominator, quantity, and shipment-count audit fields.
- Returns a deterministic, sorted, in-memory weekly metrics DataFrame.
- Rejects invalid analytical input with clear domain errors.
- Provides a read-only inspection command for manual verification.
- Adds unit, integration, and supplied-data numerical regression tests.

After Phase 3, Phase 4 should be able to calculate history and peer baselines directly from the canonical weekly metrics table.

## 3. Preconditions

Before editing, Codex must verify:

- Phase 1 foundation tests pass.
- Phase 2 ingestion and validation tests pass.
- The public Phase 2 ingestion entry point exists, such as `load_input_bundle(settings)`.
- The normalized shipment frame contains `route`, `week_of`, and `tonne_km`.
- Supplied inputs validate successfully through the Phase 2 CLI.
- The original challenge files remain unchanged.
- Existing code structure and package conventions are inspected before adding files.
- The Git working tree is inspected and unrelated changes are preserved.

If the Phase 2 public interface differs from the roadmap but is functionally equivalent, Codex should adapt to it rather than rewriting Phase 2 unnecessarily. Any material deviation must be documented in the completion report.

## 4. Canonical mathematical contract

## 4.1 Grouping key

Create one result row for each unique combination of:

```text
route
route_type
week_of
```

Important rules:

- `route` is directional and was created during Phase 2.
- Use the supplied `route_type`; do not derive it from distance.
- `week_of` must already be the Monday of the shipment's Monday-Sunday week.
- Do not add `material` or `transporter` to the grouping key.
- Shipments for different materials or transporters must contribute to the same route-week aggregate when the three canonical group keys match.

## 4.2 Weekly cost per tonne-kilometre

For each group `g`:

```text
total_freight_cost_inr_g = sum(freight_cost_inr_i)

total_tonne_km_g = sum(quantity_tonnes_i * distance_km_i)

cost_per_tonne_km_g =
    total_freight_cost_inr_g / total_tonne_km_g
```

Since Phase 2 already derives:

```text
tonne_km_i = quantity_tonnes_i * distance_km_i
```

Phase 3 should normally calculate:

```text
cost_per_tonne_km =
    sum(freight_cost_inr) / sum(tonne_km)
```

## 4.3 Forbidden calculation

Do not calculate:

```text
mean(freight_cost_inr / tonne_km)
```

An unweighted mean of shipment-level ratios gives every shipment equal influence regardless of how much freight-distance it represents. It is mathematically different from the challenge definition.

### Demonstration fixture

Use a test containing:

| Shipment | Freight cost | Quantity | Distance | Tonne-km | Shipment-level rate |
|---|---:|---:|---:|---:|---:|
| A | 100 | 10 | 10 | 100 | 1.0 |
| B | 600 | 20 | 10 | 200 | 3.0 |

Correct weighted result:

```text
(100 + 600) / (100 + 200) = 700 / 300 = 2.3333333333333335
```

Incorrect mean of ratios:

```text
(1.0 + 3.0) / 2 = 2.0
```

The unit test must prove that the implementation returns the weighted result and not `2.0`.

## 5. Input contract

The weekly analytics service must accept a normalized shipment DataFrame from Phase 2. It must not read CSV files directly.

Required columns:

```text
shipment_id
route
route_type
week_of
quantity_tonnes
distance_km
freight_cost_inr
tonne_km
```

Other validated columns may be present and should be ignored by the aggregation unless explicitly required for an audit field.

Required preconditions:

- The DataFrame is not empty.
- Required columns exist exactly once.
- Group-key values are non-null and non-blank where applicable.
- `week_of` values are valid date-like Monday values.
- `quantity_tonnes`, `distance_km`, `freight_cost_inr`, and `tonne_km` are numeric, finite, and strictly positive.
- `tonne_km` is consistent with `quantity_tonnes * distance_km` within a declared floating-point tolerance.
- `shipment_id` values are non-null and unique, as guaranteed by Phase 2.

The analytics layer should validate its own minimal preconditions but must not duplicate the complete raw-file validation pipeline from Phase 2.

## 6. Canonical weekly metrics contract

Return a new DataFrame with columns in this exact internal order:

```text
route
route_type
week_of
shipment_count
total_freight_cost_inr
total_quantity_tonnes
total_tonne_km
cost_per_tonne_km
```

### Column definitions

| Column | Meaning |
|---|---|
| `route` | Directional `origin-destination` route |
| `route_type` | Supplied route class: Short, Medium, or Long |
| `week_of` | Monday date for the grouped week |
| `shipment_count` | Number of source shipment rows contributing to the group |
| `total_freight_cost_inr` | Sum of freight cost across group shipments |
| `total_quantity_tonnes` | Sum of shipment quantity across the group |
| `total_tonne_km` | Sum of per-shipment `quantity_tonnes * distance_km` |
| `cost_per_tonne_km` | `total_freight_cost_inr / total_tonne_km` |

Requirements:

- `shipment_count` must count rows, not merely non-null values in one arbitrary column.
- `total_quantity_tonnes` is an audit metric; it is not the formula denominator.
- The denominator is `total_tonne_km`, not `total_quantity_tonnes * average_distance`.
- No output value should be rounded during calculation.
- The returned DataFrame must not share mutable state unexpectedly with the input frame.

## 7. Required project structure changes

Extend the existing backend without reorganizing unrelated Phase 1 or Phase 2 code:

```text
backend/
├── app/
│   ├── schemas/
│   │   └── analytics.py
│   └── services/
│       └── analytics/
│           ├── __init__.py
│           ├── contracts.py
│           ├── errors.py
│           └── weekly_cost.py
├── scripts/
│   └── inspect_weekly_metrics.py
└── tests/
    ├── unit/
    │   └── test_weekly_cost.py
    └── integration/
        └── test_weekly_cost_supplied_data.py
```

Codex may adapt filenames to an equivalent established project convention, but responsibilities must remain clear:

- `analytics/contracts.py`: required input columns and canonical output-column order.
- `analytics/errors.py`: focused analytics-domain exceptions.
- `analytics/weekly_cost.py`: pure weekly aggregation service.
- `schemas/analytics.py`: typed summary or inspection result models, if the project uses Pydantic for such boundaries.
- `inspect_weekly_metrics.py`: manual read-only verification command.

Do not put analytical logic in API routes, the CLI script, ingestion loaders, or a generic `utils.py` file.

## 8. Public analytics interface

Provide one clear public function, for example:

```python
def calculate_weekly_route_metrics(
    shipments: pandas.DataFrame,
) -> pandas.DataFrame:
    ...
```

Equivalent names are acceptable if they are explicit and consistent.

Requirements:

- Accept only the normalized shipment DataFrame, not a file path.
- Perform minimal analytics-boundary validation.
- Create the canonical group-level result.
- Return a new DataFrame.
- Avoid hidden writes, caches, global state, or network calls.
- Produce the same values and row order for identical logical input.
- Do not mutate the caller's DataFrame.

Optionally provide an orchestration function that accepts the Phase 2 `InputBundle`, but keep the core calculation function independently testable with a DataFrame fixture.

## 9. Analytics error design

Implement a focused exception such as:

```text
AnalyticsError
└── AnalyticsInputError
```

Use it for conditions such as:

- Empty shipment frame
- Missing analytics-required columns
- Null grouping keys
- Non-Monday `week_of`
- Non-finite or non-positive denominator inputs
- Inconsistent `tonne_km`
- Zero or non-finite aggregate denominator
- Duplicate output group keys caused by an implementation defect

Requirements:

- Error messages must name the violated contract.
- Avoid exposing entire DataFrames or complete source rows.
- Preserve original exceptions as causes where useful.
- Do not silently drop bad rows.
- Do not return a partially calculated table after a blocking error.

## 10. Required aggregation procedure

Implement the calculation in a readable sequence:

1. Validate required analytical columns.
2. Confirm the frame is non-empty.
3. Confirm every `week_of` is a Monday.
4. Confirm numeric inputs and `tonne_km` are finite and positive.
5. Confirm `tonne_km` matches quantity multiplied by distance within tolerance.
6. Create only the necessary working columns or a focused copy.
7. Group by `route`, `route_type`, and `week_of`.
8. Calculate row count and aggregate sums.
9. Verify every aggregate denominator is finite and positive.
10. Calculate `cost_per_tonne_km` from aggregated numerator and denominator.
11. Arrange columns in the canonical order.
12. Sort deterministically.
13. Run internal reconciliation checks.
14. Return a reset, stable index.

Use vectorized Pandas operations. Do not loop over all shipments when a clear groupby aggregation is sufficient.

## 11. Deterministic ordering

Sort the result using:

```text
route ascending
route_type ascending
week_of ascending
```

Use a stable sort and reset the index to a simple zero-based range.

The input row order must not influence output row order or values. Tests must shuffle the same input records and confirm an identical result after canonical sorting.

## 12. Numerical precision and rounding

Requirements:

- Preserve the source numeric precision available from Phase 2.
- Aggregate before division.
- Do not round group totals.
- Do not round `cost_per_tonne_km` in the canonical internal DataFrame.
- Do not convert rates into formatted strings.
- Use floating-point comparison tolerances in tests rather than fragile exact decimal-string comparisons.
- A recommended regression-test tolerance is `rel=1e-12` and `abs=1e-12`, unless the established environment requires a slightly wider documented tolerance.

Human-facing formatting, such as `3.30`, belongs to the submission/export or UI phase. Canonical calculation should retain a value such as `3.3012764038642617`.

Do not introduce Python `Decimal` unless there is a demonstrated correctness requirement and it can be applied consistently throughout the pipeline. The supplied dataset is well within ordinary 64-bit numerical range.

## 13. Internal reconciliation checks

Before returning, verify:

### 13.1 Shipment reconciliation

```text
sum(weekly_metrics.shipment_count) == len(shipments)
```

### 13.2 Freight-cost reconciliation

The sum of group-level `total_freight_cost_inr` must match the validated input freight-cost sum within an appropriate numerical tolerance.

### 13.3 Quantity reconciliation

The sum of group-level `total_quantity_tonnes` must match the input quantity sum within tolerance.

### 13.4 Tonne-kilometre reconciliation

The sum of group-level `total_tonne_km` must match the input `tonne_km` sum within tolerance.

### 13.5 Group-key uniqueness

No duplicate combination of `route + route_type + week_of` may exist in the result.

### 13.6 Formula reconciliation

For every row:

```text
cost_per_tonne_km ==
    total_freight_cost_inr / total_tonne_km
```

These are analytical invariants. If any fail, raise an analytics error rather than returning misleading results.

## 14. Handling edge cases

## 14.1 One shipment in a group

The weekly result should equal that shipment's cost divided by its tonne-kilometres.

## 14.2 Multiple materials and transporters

All shipments must aggregate together when their route, route type, and week match. Material and transporter are not group keys.

## 14.3 Same cities with different route types

The challenge explicitly includes `route_type` in grouping. If the same directional route appears under different valid route types, produce separate groups rather than silently merging them.

Optionally emit a diagnostic warning because such data may warrant review, but do not violate the required grouping definition.

## 14.4 Missing calendar weeks

Do not synthesize route-week rows for weeks with no shipments. Phase 3 produces only observed groups.

Do not forward-fill, interpolate, or pad missing weeks. Baseline behaviour for available weeks belongs to Phase 4.

## 14.5 Zero denominator

Phase 2 should prevent zero or negative `tonne_km`, but Phase 3 must still guard against a non-positive or non-finite aggregate denominator. Raise a blocking analytical error.

## 14.6 Floating-point noise

Use explicit tolerances for consistency and reconciliation checks. Do not round values merely to make tests pass.

## 14.7 Duplicate shipment IDs

Phase 2 owns shipment-ID validation. Phase 3 may assert uniqueness as a precondition but must not deduplicate or choose which duplicate row to keep.

## 15. Analytics inspection CLI

Create a read-only command such as:

```bash
cd backend
python -m scripts.inspect_weekly_metrics
```

It must:

1. Load settings.
2. Call the Phase 2 bundle loader.
3. Pass `bundle.shipments` to the Phase 3 analytics function.
4. Print a concise deterministic summary.
5. Exit without writing or modifying challenge files.

Suggested successful output:

```text
FreightGuard weekly analytics
Validated shipments: 2940
Weekly route groups: 728
Directional routes: 7
Route types: 3
Distinct weeks: 104
week_of range: 2024-01-01 to 2025-12-22
Reconciliation: PASS
```

Optionally print the first few canonically sorted rows. Do not print all 728 rows by default.

The command must return:

- Exit code `0` on success.
- A non-zero code for ingestion or analytics failures.
- Concise user-facing errors without an uncontrolled traceback for expected validation failures.

Do not add a CSV-writing flag in this phase. Persistent analytical output and the final submission CSV belong to later phases.

## 16. Unit-test requirements

Use small DataFrame fixtures or normalized fixture files. Unit tests must not depend only on the supplied full dataset.

## 16.1 Weighted formula test

Use the two-shipment example from Section 4.3 and assert:

```text
total_freight_cost_inr == 700
total_tonne_km == 300
cost_per_tonne_km == approximately 2.3333333333333335
cost_per_tonne_km != 2.0
```

## 16.2 Grouping tests

Test that:

- Same route, type, and week collapse into one row.
- Different routes remain separate.
- Opposite directional routes remain separate.
- Different route types remain separate.
- Different Monday weeks remain separate.
- Different materials do not create separate groups.
- Different transporters do not create separate groups.

## 16.3 Audit-field tests

Verify:

- `shipment_count` counts contributing rows.
- `total_freight_cost_inr` is the group sum.
- `total_quantity_tonnes` is the group sum.
- `total_tonne_km` is the group sum of per-shipment products.
- Canonical output columns appear in the required order.

## 16.4 Precision tests

Verify:

- No rounding occurs inside the service.
- Decimal source quantities and distances contribute accurately within tolerance.
- Rate remains numeric rather than becoming a formatted string.

## 16.5 Determinism tests

Verify:

- Result rows follow canonical sort order.
- The result index is reset.
- Shuffling input rows does not change canonical output.
- Two invocations with identical input produce equal DataFrames.

## 16.6 Immutability tests

Verify:

- Input DataFrame columns, order, values, and index remain unchanged.
- Mutating the returned result does not mutate the input.

## 16.7 Invalid-input tests

Test clear failure for:

- Empty DataFrame
- Missing required column
- Null group key
- Non-Monday `week_of`
- Zero `tonne_km`
- Negative `tonne_km`
- NaN or infinite numeric input
- Inconsistent precomputed `tonne_km`
- Duplicate shipment ID if analytics asserts this Phase 2 guarantee

## 16.8 Reconciliation-failure tests

Where practical, isolate reconciliation helpers and verify that a deliberately inconsistent result triggers an error rather than being returned.

## 17. Supplied-data integration and regression tests

Run Phase 2 ingestion against the real challenge files, then Phase 3 analytics.

The supplied dataset must produce:

```text
Input shipment rows: 2940
Weekly route groups: 728
Directional routes: 7
Route types: 3
Distinct week_of values: 104
Earliest week_of: 2024-01-01
Latest week_of: 2025-12-22
Minimum shipments in a group: 3
Maximum shipments in a group: 5
```

Assert the following numerical regression rows using full internal precision and an appropriate floating-point tolerance:

### Mumbai-Pune, week of 2024-01-01

```text
route_type = Short
shipment_count = 5
total_freight_cost_inr = 34849
total_quantity_tonnes = 70.7
total_tonne_km = 10556.220000000001
cost_per_tonne_km = 3.3012764038642617
```

### Delhi-Jaipur, week of 2024-11-11

```text
route_type = Short
shipment_count = 4
total_freight_cost_inr = 84388
total_quantity_tonnes = 72.0
total_tonne_km = 20222.59
cost_per_tonne_km = 4.1729570742422215
```

### Ahmedabad-Mumbai, week of 2025-01-20

```text
route_type = Medium
shipment_count = 5
total_freight_cost_inr = 134631
total_quantity_tonnes = 76.7
total_tonne_km = 40916.71
cost_per_tonne_km = 3.290367187391166
```

### Chennai-Bangalore, week of 2025-02-24

```text
route_type = Medium
shipment_count = 5
total_freight_cost_inr = 120133
total_quantity_tonnes = 95.5
total_tonne_km = 33530.229999999996
cost_per_tonne_km = 3.5828266015473207
```

### Mumbai-Pune, week of 2025-09-15

```text
route_type = Short
shipment_count = 4
total_freight_cost_inr = 34203
total_quantity_tonnes = 57.5
total_tonne_km = 8591.97
cost_per_tonne_km = 3.9808099888616932
```

Do not round the calculated value before performing the assertion. Use `pytest.approx` or an equivalent numerical assertion.

The integration test must also verify all four reconciliations: shipment count, freight cost, quantity, and tonne-kilometres.

## 18. Performance requirements

The supplied file is small, so correctness matters more than micro-optimization. Still:

- Use vectorized Pandas grouping.
- Avoid row-by-row Python loops for the main aggregation.
- Avoid repeated loading of the same file within one command.
- Avoid serializing intermediate DataFrames merely to calculate results.
- The full Phase 2 plus Phase 3 local pipeline should complete comfortably within a normal test timeout on a developer laptop.

Do not add parallelism, distributed computing, Dask, Spark, or caching during this phase.

## 19. Logging requirements

Use Phase 1 logging and avoid duplicate configuration.

Log:

- Analytics start and completion
- Input shipment count
- Output route-week count
- Distinct route and week counts
- Reconciliation status

Do not log:

- Entire shipment rows
- Entire weekly metrics DataFrame
- Environment secrets
- Context-note content

## 20. Documentation updates

Update only the relevant documentation.

### README

Add:

- Phase 3 implementation status
- The weighted weekly cost formula
- A warning that it is not the mean of shipment-level ratios
- Command for the weekly analytics inspection script
- Expected supplied-data summary
- Statement that baselines and anomaly flags are not implemented yet

### `docs/DECISIONS.md`

Add decisions such as:

```text
ADR-011: Aggregate numerator and denominator before division
ADR-012: Retain weekly numerator and denominator audit fields
ADR-013: Keep canonical analytics numeric and unrounded
ADR-014: Sort weekly metrics deterministically
ADR-015: Keep analytics independent from file I/O and API routes
```

### Implementation checklist

Mark Phase 3 complete only after all Phase 3 acceptance criteria pass. Do not mark Phase 4 started.

## 21. Quality and maintainability requirements

- Use type hints for public functions.
- Use named constants for input and output column contracts.
- Keep calculation logic independent from the CLI.
- Keep calculation logic independent from FastAPI.
- Use pure or nearly pure functions where practical.
- Do not mutate the Phase 2 `InputBundle` or its shipment frame.
- Avoid chained assignments and ambiguous Pandas view mutation.
- Do not hide the formula inside an opaque one-line expression.
- Keep reconciliation logic explicit and testable.
- Do not duplicate Phase 2 CSV-loading code.
- Do not add a generic `utils.py` module.
- Preserve all existing Phase 1 and Phase 2 tests.
- Preserve original input files byte-for-byte.

## 22. Explicit non-goals for Phase 3

Codex must not implement:

- Trailing eight-week own-history baselines
- Same-week similar-route peer baselines
- Percentage deviations
- Candidate anomaly rules or thresholds
- Flagged verdicts
- Submission CSV generation
- Context-note semantic parsing
- Note-date interval extraction
- Embeddings or vector search
- Evidence matching or Evidence Gate logic
- LLM integration or explanations
- Token or cost logging
- New FastAPI analysis endpoints
- File uploads
- Database persistence
- React frontend initialization
- Charts or dashboards
- Docker configuration
- Natural-language Q&A

Do not create placeholder baseline or anomaly columns in the weekly metrics DataFrame. Phase 4 and Phase 5 own those fields.

## 23. Required verification commands

Codex must adapt these commands to the repository's established environment and report the exact commands that succeeded.

### Run the complete backend test suite

```bash
python -m pytest backend/tests -q
```

### Run Phase 3 tests with coverage

```bash
python -m pytest \
  backend/tests/unit/test_weekly_cost.py \
  backend/tests/integration/test_weekly_cost_supplied_data.py \
  -q --cov=backend/app/services/analytics
```

For Windows PowerShell, Codex may place the command on one line:

```powershell
python -m pytest backend/tests/unit/test_weekly_cost.py backend/tests/integration/test_weekly_cost_supplied_data.py -q --cov=backend/app/services/analytics
```

Adjust coverage import paths to the actual package layout without weakening the tested scope.

### Lint

```bash
python -m ruff check backend
```

### Validate inputs before analytics

```bash
cd backend
python -m scripts.validate_inputs
```

### Inspect weekly metrics

```bash
cd backend
python -m scripts.inspect_weekly_metrics
```

For Windows PowerShell:

```powershell
Set-Location backend
python -m scripts.validate_inputs
python -m scripts.inspect_weekly_metrics
```

No server or command may be left waiting indefinitely.

## 24. Acceptance criteria

Phase 3 is complete only when every applicable condition is satisfied:

- [x] Phase 1 and Phase 2 tests still pass.
- [x] Analytics consumes the Phase 2 normalized shipment frame rather than reading CSV directly.
- [x] Required analytics input columns are centralized and checked.
- [x] Weekly metrics are grouped by `route + route_type + week_of` exactly.
- [x] Materials and transporters are not accidental grouping keys.
- [x] `shipment_count` counts every contributing row.
- [x] `total_freight_cost_inr` is calculated correctly.
- [x] `total_quantity_tonnes` is calculated correctly.
- [x] `total_tonne_km` is the sum of per-shipment tonne-kilometres.
- [x] `cost_per_tonne_km` divides the aggregated cost by aggregated tonne-kilometres.
- [x] The service does not calculate the mean of shipment-level ratios.
- [x] Canonical output columns appear in the required internal order.
- [x] Internal numerical values remain unrounded.
- [x] Output is sorted deterministically and uses a reset index.
- [x] Input DataFrame is not mutated.
- [x] Empty or invalid analytical input fails clearly.
- [x] Non-Monday weeks and invalid denominators are rejected.
- [x] Shipment, cost, quantity, and tonne-kilometre reconciliations pass.
- [x] Output group keys are unique.
- [x] Shuffled input produces identical canonical output.
- [x] Supplied data produces exactly 728 weekly route groups.
- [x] Supplied data covers seven directional routes, three route types, and 104 weeks.
- [x] Supplied weekly range is 2024-01-01 through 2025-12-22.
- [x] All five supplied-data numerical regression cases pass within tolerance.
- [x] The inspection CLI prints a concise successful summary without writing files.
- [x] README and architectural decisions are updated.
- [x] Ruff reports no errors.
- [x] No Phase 4 or later functionality is implemented.
- [x] Codex reports changes, commands, exact results, limitations, and a commit message.
- [x] Codex stops after Phase 3.

## 25. Suggested Phase 3 commit message

```text
feat: add deterministic weekly freight cost analytics
```

## 26. Copy-paste instruction for Codex

```text
Read AGENTS.md, docs/PROJECT_SPEC.md, docs/IMPLEMENTATION_PLAN.md,
docs/DECISIONS.md, FREIGHTGUARD_MASTER_IMPLEMENTATION_ROADMAP.md,
FREIGHTGUARD_PHASE_2_DATA_INGESTION_VALIDATION_PLAN.md, and
FREIGHTGUARD_PHASE_3_WEEKLY_COST_ANALYTICS_PLAN.md completely before editing.

Inspect the repository and verify that Phases 1 and 2 are complete. Preserve
all unrelated existing work and adapt to established package conventions
without rewriting working Phase 2 ingestion code.

Implement Phase 3 only according to
FREIGHTGUARD_PHASE_3_WEEKLY_COST_ANALYTICS_PLAN.md.

Create a dedicated analytics service that consumes the validated normalized
shipment DataFrame from Phase 2. Group by route, route_type, and week_of. Retain
shipment_count, total_freight_cost_inr, total_quantity_tonnes, and
total_tonne_km. Calculate cost_per_tonne_km as aggregated freight cost divided
by aggregated tonne-kilometres.

Do not calculate the mean of shipment-level rates. Do not round canonical
values. Do not mutate the input DataFrame. Do not add direct CSV reads inside
the analytics service.

Add analytical reconciliation checks, deterministic sorting, focused unit
tests, supplied-data regression tests, and a read-only weekly metrics
inspection command.

Do not implement history baselines, peer baselines, deviations, anomaly flags,
submission CSV generation, context-note interpretation, retrieval, LLM
features, new analysis API endpoints, React, databases, or Docker.

Run the complete existing backend test suite, focused Phase 3 tests with
coverage, Ruff, the Phase 2 validation command, and the Phase 3 inspection
command using sensible timeouts.

When finished, report:

1. What was implemented
2. Every file created or modified
3. Important engineering decisions and deviations from this plan
4. Commands executed and their exact results
5. Supplied-data analytics counts and regression values
6. Reconciliation results
7. Exact manual verification steps
8. Any limitations or blockers
9. A concise Git commit message

Update the Phase 3 checklist, then stop. Do not begin Phase 4.
```
