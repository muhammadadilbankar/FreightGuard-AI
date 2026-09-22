# FreightGuard AI - Phase 4 Baseline Engine Implementation Plan

## 1. Purpose of this document

This document is the complete implementation contract for Phase 4 of FreightGuard AI. Give it to Codex together with the master roadmap and the completed Phase 3 weekly analytics plan after Phases 1 through 3 have been tested and committed.

Phase 4 enriches each canonical weekly route metric with two comparison baselines required by the challenge:

1. The route group's trailing eight-week own-history average, using only prior observations.
2. The same-week average of all other routes sharing the same `route_type`.

This phase is specifically designed to prevent look-ahead leakage and self-inclusion. It retains audit counts showing exactly how many historical weeks and peer routes contributed to each baseline.

Phase 4 does not calculate percentage deviations, anomaly candidates, flags, contextual verdicts, explanations, or the final submission CSV.

## 2. Phase objective

Build a deterministic baseline service that:

- Consumes the canonical weekly metrics DataFrame created by Phase 3.
- Preserves every Phase 3 row and canonical value.
- Calculates the own-history baseline using at most eight strictly prior route-week observations.
- Handles early route history using all prior observations available.
- Calculates the same-week route-type peer average while excluding the current route.
- Records `history_weeks_used` and `peer_routes_used` for auditability.
- Returns a stable, sorted, unrounded in-memory DataFrame.
- Handles unavailable baselines explicitly without guessing, padding, or self-comparison.
- Provides a read-only inspection command.
- Adds leakage, exclusion, edge-case, determinism, and supplied-data regression tests.

After Phase 4, Phase 5 should be able to calculate percentage deviations, apply the configured anomaly rule, and generate the initial submission-shaped output.

## 3. Preconditions

Before editing, Codex must verify:

- Phase 1 foundation tests pass.
- Phase 2 ingestion and validation tests pass.
- Phase 3 weekly analytics tests pass.
- The Phase 2 public bundle loader works against the supplied files.
- The Phase 3 public weekly analytics function exists and returns its canonical schema.
- The Phase 3 inspection command reports 728 weekly route groups for the supplied data.
- Original challenge input files remain unchanged.
- Existing package conventions are inspected before adding modules.
- The Git working tree is inspected and unrelated changes are preserved.

If equivalent interfaces use different names, adapt to them rather than rewriting correct earlier-phase code. Report any material deviation from the documented architecture.

## 4. Input contract

The baseline service must accept the canonical Phase 3 weekly metrics DataFrame, not shipment-level records and not a CSV path.

Required columns in canonical order:

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

Required preconditions:

- The DataFrame is not empty.
- Every required column exists exactly once.
- `route`, `route_type`, and `week_of` contain no null values.
- `route` values are non-blank directional identifiers.
- `route_type` contains only canonical values established by Phase 2.
- Every `week_of` value is a valid Monday date.
- Every `cost_per_tonne_km` is numeric, finite, and strictly positive.
- Every combination of `route + route_type + week_of` is unique.
- Phase 3 audit values remain valid.

The service may assert these minimal boundary conditions but must not reload or revalidate the raw shipment CSV.

## 5. Own-history baseline contract

## 5.1 Partition key

Calculate own history separately for each:

```text
route + route_type
```

The challenge defines analysis groups using both route and route type. If the same directional route appears under different route types, their histories must remain separate.

## 5.2 Ordering

Within each route group, order observations by `week_of` ascending before any rolling calculation.

Input row order must not influence the baseline.

## 5.3 Baseline definition

For current observation `t`, use:

```text
own_history_avg_cost_per_tonne_km_t =
    mean(cost_per_tonne_km for the previous at most 8
         available observations of the same route + route_type)
```

The current observation must be excluded before rolling.

Conceptually:

```text
shift current value out
then rolling mean over the previous 8 available values
```

Equivalent Pandas logic may use:

```python
series.shift(1).rolling(window=8, min_periods=1).mean()
```

The implementation may use a different vectorized form if tests prove identical semantics.

## 5.4 Early-history behaviour

- First observation for a route group: no prior history exists.
  - Baseline must be missing (`NaN` or the project's canonical numeric missing representation).
  - `history_weeks_used = 0`.
- Second observation: use the first observation only.
  - `history_weeks_used = 1`.
- Continue using all available prior observations until eight exist.
- Ninth and later observations: use exactly the previous eight available route-week observations.
  - `history_weeks_used = 8`.

Do not:

- Fill the first baseline with the current value.
- Fill it with zero.
- Backfill from future observations.
- Extrapolate a value.
- Pad missing weeks.

## 5.5 Meaning of “previous eight weeks”

For this project, follow the master roadmap's contract: use the previous eight available weekly observations for that `route + route_type` group.

If a route has a calendar week with no shipments, Phase 3 does not synthesize a row. Phase 4 must not synthesize one either. Use the previous eight observed route-week values, ordered by `week_of`.

Document this interpretation clearly in the README because the supplied dataset happens to have continuous weekly observations, while future data may not.

## 5.6 No-look-ahead invariant

For every non-null own-history baseline:

```text
max(contributing week_of) < current week_of
```

No current-week or future value may influence the baseline.

Changing a future weekly cost must not alter an earlier row's baseline. Unit tests must demonstrate this explicitly.

## 5.7 `history_weeks_used`

Store the number of prior values used:

```text
history_weeks_used = min(number of prior observations, 8)
```

Required type:

- Integer
- Never negative
- Always between `0` and `8`
- Equal to zero exactly when the own-history baseline is unavailable

## 6. Similar-route peer baseline contract

## 6.1 Peer group

For current route-week row `r`, candidate peers are rows that share:

```text
same route_type
same week_of
```

The current route group must be excluded.

## 6.2 Peer baseline definition

```text
similar_routes_avg_cost_per_tonne_km_r =
    arithmetic mean(cost_per_tonne_km of all other matching routes)
```

This is a simple arithmetic mean of route-level weekly rates.

Do not:

- Include the current route.
- Recalculate a pooled ratio from peer freight cost and peer tonne-kilometres.
- Weight routes by shipment count.
- Weight routes by quantity.
- Weight routes by tonne-kilometres.
- Compare against other route types.
- Compare against different weeks.

## 6.3 Efficient exclusion

A transparent vectorized implementation can calculate, for each `route_type + week_of` group:

```text
group_rate_sum
group_route_count

peer_rate_sum = group_rate_sum - current_route_rate
peer_routes_used = group_route_count - 1

peer_average = peer_rate_sum / peer_routes_used
```

Mask `peer_average` as missing when `peer_routes_used == 0`.

This pattern is acceptable only after confirming Phase 3 group keys are unique.

## 6.4 No-peer behaviour

If a route has no other route in the same `route_type` and week:

- `similar_routes_avg_cost_per_tonne_km` must be missing.
- `peer_routes_used = 0`.
- Do not use the current route as its own peer.
- Do not borrow peers from another week or route type.
- Do not substitute its own history.

Phase 5 must later treat an unavailable peer comparison explicitly rather than converting it to a zero-percent deviation.

## 6.5 `peer_routes_used`

Store the number of other route-level weekly rows contributing to the peer average.

Required type:

- Integer
- Never negative
- Equal to zero exactly when the peer baseline is unavailable
- Equal to the matching route-type/week group size minus one

## 7. Demonstration fixtures

## 7.1 Own-history fixture

For one route group with weekly costs:

```text
Week 1: 1.0
Week 2: 2.0
Week 3: 3.0
Week 4: 4.0
Week 5: 5.0
Week 6: 6.0
Week 7: 7.0
Week 8: 8.0
Week 9: 9.0
Week 10: 10.0
```

Expected results:

| Current week | History values | Baseline | Weeks used |
|---|---|---:|---:|
| Week 1 | None | Missing | 0 |
| Week 2 | 1 | 1.0 | 1 |
| Week 3 | 1, 2 | 1.5 | 2 |
| Week 9 | 1 through 8 | 4.5 | 8 |
| Week 10 | 2 through 9 | 5.5 | 8 |

The Week 10 baseline must not contain the Week 10 value.

## 7.2 Peer fixture

For three Short routes in the same week:

```text
Route A rate = 2.0
Route B rate = 4.0
Route C rate = 8.0
```

Expected peer baselines:

| Current route | Peer rates | Peer average | Peers used |
|---|---|---:|---:|
| Route A | 4.0, 8.0 | 6.0 | 2 |
| Route B | 2.0, 8.0 | 5.0 | 2 |
| Route C | 2.0, 4.0 | 3.0 | 2 |

Add a Long route in the same week with no other Long route:

```text
peer average = Missing
peer_routes_used = 0
```

## 7.3 Unweighted peer proof

Give peer routes very different shipment counts or `total_tonne_km` values while retaining rates of `4.0` and `8.0`. Route A's peer baseline must remain `6.0`.

This proves the implementation averages route-level rates rather than pooling or weighting them.

## 8. Canonical enriched output contract

Return a new DataFrame with the Phase 3 columns preserved and four Phase 4 columns appended in this order:

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

Requirements:

- Preserve all 728 supplied-data rows.
- Preserve Phase 3 values without rounding or recalculation drift.
- Keep baseline values numeric and unrounded.
- Keep audit counts as integers.
- Keep unavailable baselines as missing numeric values, not strings such as `N/A`.
- Do not add percentage-deviation or flag columns in this phase.

## 9. Required project structure changes

Extend the existing analytics module without reorganizing working earlier-phase files:

```text
backend/
├── app/
│   └── services/
│       └── analytics/
│           ├── contracts.py
│           ├── errors.py
│           ├── weekly_cost.py
│           └── baselines.py
├── scripts/
│   └── inspect_baselines.py
└── tests/
    ├── unit/
    │   └── test_baselines.py
    └── integration/
        └── test_baselines_supplied_data.py
```

Responsibilities:

- `baselines.py`: baseline calculation and focused invariants.
- Existing `contracts.py`: extend with Phase 4 required/output columns rather than scattering literals.
- Existing `errors.py`: reuse the analytics error hierarchy when appropriate.
- `inspect_baselines.py`: compose Phases 2, 3, and 4 for manual inspection.
- Tests: isolate baseline behaviour from ingestion wherever possible.

Do not create a second analytics package, duplicate Phase 3 calculation code, or move working files without a clear need.

## 10. Public baseline interface

Provide one explicit function, for example:

```python
def add_comparison_baselines(
    weekly_metrics: pandas.DataFrame,
) -> pandas.DataFrame:
    ...
```

Equivalent naming is acceptable if it is clear and consistent.

Requirements:

- Accept the Phase 3 weekly metrics DataFrame.
- Perform minimal boundary validation.
- Sort a working copy before window calculations.
- Add the four canonical Phase 4 fields.
- Return a new DataFrame.
- Preserve all Phase 3 rows and values.
- Avoid file reads, writes, network calls, caches, or global mutable state.
- Do not mutate the caller's DataFrame.
- Produce identical canonical output for logically identical input.

Optionally provide an orchestration function that composes the Phase 2 bundle loader and Phase 3 weekly analytics, but keep the baseline calculation independently testable with a Phase 3-shaped fixture.

## 11. Required calculation procedure

Implement the baseline calculation in a readable sequence:

1. Validate Phase 3 required columns.
2. Confirm the input is non-empty.
3. Confirm the Phase 3 group key is unique.
4. Confirm `week_of` values are Mondays.
5. Confirm `cost_per_tonne_km` is numeric, finite, and positive.
6. Create a working copy.
7. Sort by `route`, `route_type`, and `week_of` using a stable sort.
8. Partition by `route + route_type`.
9. Shift current cost out of the own-history series.
10. Calculate rolling means over at most eight prior available observations.
11. Calculate `history_weeks_used`.
12. Group by `route_type + week_of` for peer calculations.
13. Subtract the current route rate and one route from peer totals.
14. Calculate peer averages where at least one peer exists.
15. Set unavailable peer baselines to missing.
16. Arrange columns in canonical Phase 4 order.
17. Run invariants and reconciliation checks.
18. Return the stable sorted result with a reset index.

Use vectorized Pandas operations. A small group-level transform is acceptable; row-by-row Python loops over the full table are unnecessary.

## 12. Determinism and ordering

Canonical sort order remains:

```text
route ascending
route_type ascending
week_of ascending
```

Requirements:

- Use a stable sort.
- Reset the returned index.
- Shuffling the Phase 3 input rows must not change output values or row order.
- Re-running with identical input must produce an equal DataFrame.
- Missing numerical baselines must appear consistently.

## 13. Numerical precision

- Do not round Phase 3 values.
- Do not round baseline averages.
- Do not convert baseline values into formatted percentage strings.
- Use floating-point tolerance in tests.
- Recommended regression tolerance: `rel=1e-12`, `abs=1e-12`, unless a slightly wider tolerance is required and documented.
- Do not use rounding to hide an inclusion or windowing error.

Percentage deviations and display strings belong to Phase 5.

## 14. Baseline invariants and reconciliation

Before returning, verify:

## 14.1 Row preservation

```text
len(enriched_metrics) == len(weekly_metrics)
```

## 14.2 Key preservation

Every Phase 3 `route + route_type + week_of` key appears exactly once in the enriched result, with no added or removed key.

## 14.3 Phase 3 value preservation

All Phase 3 columns remain equal to their canonical input values after sorting and index normalization.

## 14.4 History-count bounds

```text
0 <= history_weeks_used <= 8
```

## 14.5 History availability consistency

```text
history_weeks_used == 0
if and only if
own_history_avg_cost_per_tonne_km is missing
```

## 14.6 Peer-count bounds

```text
peer_routes_used >= 0
```

## 14.7 Peer availability consistency

```text
peer_routes_used == 0
if and only if
similar_routes_avg_cost_per_tonne_km is missing
```

## 14.8 Baseline finiteness

Every available baseline must be finite and strictly positive.

## 14.9 No self-inclusion

For a two-route peer group, each route's peer baseline must exactly equal the other route's rate within tolerance.

## 14.10 No look-ahead

For a route row at week `t`, changing any row with week greater than or equal to `t` must not change its own-history baseline at `t`.

If an invariant fails, raise an analytics error rather than returning a partially trustworthy table.

## 15. Error handling

Reuse the Phase 3 analytics exception hierarchy when possible, such as:

```text
AnalyticsError
└── AnalyticsInputError
```

Raise a focused error for:

- Empty weekly metrics input
- Missing Phase 3 column
- Duplicate Phase 3 group key
- Null group key
- Non-Monday week
- Invalid current cost
- Inconsistent history counts
- Inconsistent peer counts
- Failed row/key preservation
- Non-finite calculated baseline

Requirements:

- Name the violated contract clearly.
- Do not print entire DataFrames or complete source rows.
- Do not silently drop duplicate groups.
- Do not fill invalid results with zero.
- Do not catch and suppress unexpected exceptions broadly.

## 16. Baseline inspection CLI

Create a read-only command such as:

```bash
cd backend
python -m scripts.inspect_baselines
```

It must:

1. Load the validated Phase 2 input bundle.
2. Calculate Phase 3 weekly metrics.
3. Add Phase 4 baselines.
4. Print a concise deterministic summary.
5. Exit without writing CSV or modifying inputs.

Suggested supplied-data output:

```text
FreightGuard baseline engine
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

Optionally print a few named regression rows. Do not print the entire table by default.

The command must return zero on success and a non-zero exit code for ingestion or analytics errors. Handle expected domain errors concisely.

Do not add file export in this phase.

## 17. Unit-test requirements

Use small Phase 3-shaped DataFrame fixtures. Unit tests must not depend exclusively on the supplied full dataset.

## 17.1 Own-history tests

Test:

- First observation baseline is missing with count zero.
- Second observation uses exactly one prior value.
- Early rows use all prior values available.
- Ninth observation uses the previous eight.
- Tenth observation drops the oldest and uses observations two through nine.
- Current value never contributes to its own baseline.
- Route histories do not mix.
- Route types do not mix for the same route name.

## 17.2 Leakage tests

Test:

- Changing the current row's cost does not change its own-history baseline.
- Changing a future row does not change any earlier own-history baseline.
- Changing a past contributing row changes only appropriate later windows.
- A row more than eight prior observations back does not affect the current full-window baseline.

## 17.3 Missing-week tests

Create a route with gaps in `week_of` and verify that the previous eight available observed route-weeks are used without synthesizing missing rows.

## 17.4 Peer tests

Test:

- Current route is excluded.
- Peer average uses only the same route type.
- Peer average uses only the same week.
- Three-route example produces 6.0, 5.0, and 3.0.
- A two-route group gives each route the other's exact rate.
- One-route group returns missing baseline and peer count zero.
- Different peer shipment counts do not weight the average.
- Different peer tonne-kilometres do not weight the average.

## 17.5 Audit-count tests

Test:

- `history_weeks_used` sequence grows from zero to eight and stays at eight.
- `peer_routes_used` equals matching group size minus one.
- Audit counts are integer-valued.
- Missing-baseline and zero-count equivalences hold.

## 17.6 Determinism tests

Test:

- Shuffled input yields identical canonical output.
- Repeated calls yield equal output.
- Output order and index are stable.

## 17.7 Immutability tests

Test:

- Phase 3 input DataFrame is unchanged.
- Mutating returned Phase 4 output does not mutate Phase 3 input.

## 17.8 Invalid-input tests

Test clear failure for:

- Empty DataFrame
- Missing required column
- Duplicate route/type/week key
- Null group key
- Non-Monday week
- Zero, negative, NaN, or infinite current cost

## 18. Supplied-data integration and regression tests

Compose the actual Phase 2, Phase 3, and Phase 4 services against the supplied challenge files.

Expected supplied-data baseline summary:

```text
Rows preserved: 728
Own-history baseline missing: 7
Own-history baseline available: 721
history_weeks_used = 0: 7 rows
history_weeks_used = 1 through 7: 7 rows for each count
history_weeks_used = 8: 672 rows
Peer baseline missing: 0
peer_routes_used = 1: 416 rows
peer_routes_used = 2: 312 rows
```

Use full precision with numerical tolerance for the following regression cases.

## 18.1 Mumbai-Pune, week of 2024-01-01

```text
cost_per_tonne_km = 3.3012764038642617
own_history_avg_cost_per_tonne_km = Missing
history_weeks_used = 0
similar_routes_avg_cost_per_tonne_km = 3.000124589086287
peer_routes_used = 1
```

## 18.2 Mumbai-Pune, week of 2024-01-08

```text
cost_per_tonne_km = 3.3819401535881366
own_history_avg_cost_per_tonne_km = 3.3012764038642617
history_weeks_used = 1
similar_routes_avg_cost_per_tonne_km = 3.053238844499479
peer_routes_used = 1
```

## 18.3 Mumbai-Pune, week of 2024-02-26

```text
cost_per_tonne_km = 3.249925923123964
own_history_avg_cost_per_tonne_km = 3.3380877267885767
history_weeks_used = 8
similar_routes_avg_cost_per_tonne_km = 3.0959226120172616
peer_routes_used = 1
```

## 18.4 Delhi-Jaipur, week of 2024-11-11

```text
cost_per_tonne_km = 4.1729570742422215
own_history_avg_cost_per_tonne_km = 3.079216557951722
history_weeks_used = 8
similar_routes_avg_cost_per_tonne_km = 3.447745798728505
peer_routes_used = 1
```

Reference comparisons, to be computed only inside the regression test or manual verification and not persisted as Phase 4 columns:

```text
vs own history = approximately +35.52009076679068 percent
vs similar routes = approximately +21.034360357459292 percent
```

## 18.5 Ahmedabad-Mumbai, week of 2025-01-20

```text
cost_per_tonne_km = 3.290367187391166
own_history_avg_cost_per_tonne_km = 2.541351823620185
history_weeks_used = 8
similar_routes_avg_cost_per_tonne_km = 2.6861515905915425
peer_routes_used = 2
```

Reference comparisons:

```text
vs own history = approximately +29.473107847932667 percent
vs similar routes = approximately +22.49372667260985 percent
```

## 18.6 Chennai-Bangalore, week of 2025-02-24

```text
cost_per_tonne_km = 3.5828266015473207
own_history_avg_cost_per_tonne_km = 2.7253267565207007
history_weeks_used = 8
similar_routes_avg_cost_per_tonne_km = 2.5837434925863763
peer_routes_used = 2
```

Reference comparisons:

```text
vs own history = approximately +31.46411133912437 percent
vs similar routes = approximately +38.6680454862353 percent
```

## 18.7 Mumbai-Pune, week of 2025-09-15

```text
cost_per_tonne_km = 3.9808099888616932
own_history_avg_cost_per_tonne_km = 3.643772458181048
history_weeks_used = 8
similar_routes_avg_cost_per_tonne_km = 3.220063126502312
peer_routes_used = 1
```

Reference comparisons:

```text
vs own history = approximately +9.24968654186744 percent
vs similar routes = approximately +23.625215794626907 percent
```

The reference percentages confirm the baselines against the supplied sample examples. Phase 4 must not add percentage-deviation columns; those belong to Phase 5.

## 19. Performance requirements

- Use vectorized Pandas groupby, transform, shift, and rolling operations.
- Avoid nested Python loops over routes and weeks.
- Do not reload input files inside the baseline function.
- Do not serialize intermediate tables.
- Do not add multiprocessing, Spark, Dask, a database, or a cache.
- The complete Phase 2 through Phase 4 pipeline should run comfortably within ordinary local test timeouts.

Correct window semantics are more important than micro-optimization.

## 20. Logging requirements

Use the existing logging configuration.

Log concise metrics such as:

- Baseline calculation start and completion
- Weekly rows received and returned
- Count of available and unavailable own-history baselines
- Count of available and unavailable peer baselines
- Minimum and maximum history/peer counts
- Invariant status

Do not log:

- Entire DataFrames
- All baseline rows
- Context-note text
- Environment secrets

## 21. Documentation updates

Update only relevant documentation.

### README

Add:

- Phase 4 status
- Exact own-history definition
- Exact same-week peer definition
- Statement that current week is excluded from own history
- Statement that current route is excluded from peer average
- Early-history and no-peer behaviour
- Baseline inspection command and expected summary
- Statement that percentage deviations and flags remain Phase 5 work

### `docs/DECISIONS.md`

Add decisions such as:

```text
ADR-016: Shift before applying the trailing eight-observation window
ADR-017: Use available prior route-week observations without padding
ADR-018: Average peer route-level rates without weighting
ADR-019: Exclude the current route from its peer baseline
ADR-020: Represent unavailable baselines as missing with explicit audit counts
```

### Implementation checklist

Mark Phase 4 complete only after all acceptance criteria pass. Do not mark Phase 5 started.

## 22. Quality and maintainability requirements

- Use type hints for public functions.
- Keep baseline logic independent from CLI and FastAPI.
- Reuse Phase 3 contracts and errors appropriately.
- Keep baseline column names centralized.
- Prefer vectorized and readable Pandas operations.
- Keep own-history and peer calculations separately testable.
- Preserve input immutability.
- Preserve Phase 3 columns and values.
- Avoid chained assignment and ambiguous DataFrame views.
- Do not replace missing baselines with strings or zeros.
- Do not duplicate Phase 2 loading or Phase 3 aggregation.
- Do not add a generic `utils.py` module.
- Preserve all earlier tests and input-file hashes.

## 23. Explicit non-goals for Phase 4

Codex must not implement:

- `vs_own_history_pct`
- `vs_similar_routes_pct`
- Percentage-format strings
- Candidate anomaly thresholds
- Candidate or final flags
- `matched_note_id`
- Reason generation
- Submission CSV generation
- Context-note semantic parsing
- Effective note-date ranges
- Embeddings or vector retrieval
- Evidence Gate logic
- LLM integration
- Token or cost logging
- New FastAPI analysis endpoints
- Database persistence
- React frontend or charts
- Docker configuration
- Natural-language Q&A

Do not add placeholder flag or explanation columns. Phase 5 owns comparisons, candidate detection, and the initial submission-shaped output.

## 24. Required verification commands

Codex must adapt commands to the established repository and report the exact commands that succeeded.

### Complete backend test suite

```bash
python -m pytest backend/tests -q
```

### Focused Phase 4 tests with coverage

```bash
python -m pytest \
  backend/tests/unit/test_baselines.py \
  backend/tests/integration/test_baselines_supplied_data.py \
  -q --cov=backend/app/services/analytics
```

Windows PowerShell equivalent may be written on one line:

```powershell
python -m pytest backend/tests/unit/test_baselines.py backend/tests/integration/test_baselines_supplied_data.py -q --cov=backend/app/services/analytics
```

### Lint

```bash
python -m ruff check backend
```

### Validate and inspect the complete pipeline

```bash
cd backend
python -m scripts.validate_inputs
python -m scripts.inspect_weekly_metrics
python -m scripts.inspect_baselines
```

For Windows PowerShell:

```powershell
Set-Location backend
python -m scripts.validate_inputs
python -m scripts.inspect_weekly_metrics
python -m scripts.inspect_baselines
```

No server or command may be left waiting indefinitely.

## 25. Acceptance criteria

Phase 4 is complete only when every applicable condition is satisfied:

- [x] All Phase 1 through Phase 3 tests still pass.
- [x] The baseline service consumes Phase 3 weekly metrics rather than raw CSV or shipment rows.
- [x] The Phase 3 group key is validated as unique.
- [x] Own history is partitioned by `route + route_type`.
- [x] Current week is excluded before rolling.
- [x] No future value contributes to an earlier baseline.
- [x] At most eight prior available observations contribute.
- [x] Early rows use every prior observation available.
- [x] First route observation has missing history baseline and count zero.
- [x] `history_weeks_used` remains between zero and eight.
- [x] Missing calendar weeks are not synthesized or padded.
- [x] Peer groups use the same `route_type` and `week_of` only.
- [x] Current route is excluded from its peer baseline.
- [x] Peer baseline is an unweighted arithmetic mean of route-level rates.
- [x] A route is never used as its own peer.
- [x] No-peer rows have missing peer baseline and count zero.
- [x] Audit counts are integer-valued and consistent with baseline availability.
- [x] Phase 3 rows, keys, columns, and values are preserved.
- [x] Canonical Phase 4 columns appear in the required order.
- [x] Baseline values remain numeric and unrounded.
- [x] Input DataFrame is not mutated.
- [x] Shuffled input yields identical canonical output.
- [x] Supplied data preserves exactly 728 rows.
- [x] Supplied data has exactly seven missing own-history baselines.
- [x] Supplied data has 672 rows using a full eight-week history.
- [x] Supplied data has no missing peer baselines.
- [x] Supplied peer-count distribution is 416 rows with one peer and 312 rows with two peers.
- [x] All supplied-data regression cases pass within tolerance.
- [x] Baseline inspection CLI reports successful leakage and self-exclusion checks.
- [x] README and architectural decisions are updated.
- [x] Ruff reports no errors.
- [x] No Phase 5 or later functionality is implemented.
- [x] Codex reports files, decisions, commands, exact results, limitations, and a commit message.
- [x] Codex stops after Phase 4.

## 26. Suggested Phase 4 commit message

```text
feat: add leak-free history and peer baselines
```

## 27. Copy-paste instruction for Codex

```text
Read AGENTS.md, docs/PROJECT_SPEC.md, docs/IMPLEMENTATION_PLAN.md,
docs/DECISIONS.md, FREIGHTGUARD_MASTER_IMPLEMENTATION_ROADMAP.md,
FREIGHTGUARD_PHASE_3_WEEKLY_COST_ANALYTICS_PLAN.md, and
FREIGHTGUARD_PHASE_4_BASELINE_ENGINE_PLAN.md completely before editing.

Inspect the repository and verify that Phases 1 through 3 are complete.
Preserve unrelated work and adapt to established package conventions without
rewriting correct ingestion or weekly analytics code.

Implement Phase 4 only according to
FREIGHTGUARD_PHASE_4_BASELINE_ENGINE_PLAN.md.

Create a baseline service that consumes the canonical Phase 3 weekly metrics
DataFrame. For each route + route_type group, calculate the mean of at most the
previous eight available weekly cost_per_tonne_km values after shifting the
current value out. Record history_weeks_used.

For every route-week, calculate the arithmetic mean of other route-level rates
sharing the same route_type and week_of. Exclude the current route and record
peer_routes_used. Do not weight peer rates by shipments, quantity, freight
cost, or tonne-kilometres.

Preserve all Phase 3 rows and values. Keep baseline values numeric and
unrounded. Represent unavailable baselines as missing with an audit count of
zero. Do not mutate the input DataFrame.

Add no-look-ahead, self-exclusion, early-history, missing-week, no-peer,
unweighted-peer, determinism, immutability, and supplied-data regression tests.
Add a read-only baseline inspection command.

Do not implement percentage deviations, threshold rules, anomaly flags,
matched notes, reasons, submission CSV generation, context-note intelligence,
retrieval, LLM features, API analysis endpoints, React, databases, or Docker.

Run the complete backend test suite, focused Phase 4 tests with coverage, Ruff,
the Phase 2 validation command, the Phase 3 inspection command, and the Phase 4
inspection command with sensible timeouts.

When finished, report:

1. What was implemented
2. Every file created or modified
3. Important engineering decisions and deviations from this plan
4. Commands executed and exact results
5. Supplied-data baseline counts and regression values
6. No-look-ahead and peer self-exclusion evidence
7. Exact manual verification steps
8. Any limitations or blockers
9. A concise Git commit message

Update the Phase 4 checklist, then stop. Do not begin Phase 5.
```
