# Architecture decision log

## ADR-001: Use weighted aggregate cost per tonne-km

- **Status:** Accepted
- **Context:** A mean of per-shipment ratios overweights small shipments.
- **Decision:** Divide total freight cost by total tonne-kilometres per route-week.
- **Consequences:** Results represent transported volume and require numerator and
  denominator aggregation before division.

## ADR-002: Separate deterministic decisions from AI wording

- **Status:** Accepted
- **Context:** Canonical results must be auditable and reproducible.
- **Decision:** Deterministic code owns calculations, evidence selection, note IDs,
  and verdicts; AI may only phrase an already validated packet.
- **Consequences:** AI failures cannot alter canonical results, and fallback wording
  remains possible.

## ADR-003: Use Monday as `week_of`

- **Status:** Accepted
- **Context:** Weekly grouping needs one unambiguous calendar convention.
- **Decision:** Weeks run Monday through Sunday and use Monday as their identifier.
- **Consequences:** Every shipment date maps deterministically to one week.

## ADR-004: Keep anomaly threshold configurable

- **Status:** Accepted
- **Context:** The challenge does not prescribe a threshold.
- **Decision:** Default to 20 percent and expose a validated non-negative setting.
- **Consequences:** Sensitivity can change without code edits; the active value must
  be captured for reproducible runs.

## ADR-005: Delay frontend and AI dependencies

- **Status:** Accepted
- **Context:** Foundation work should stay small and testable.
- **Decision:** Add no frontend, analytics, retrieval, database, or LLM dependency
  before its designated phase.
- **Consequences:** Phase 1 installs quickly and cannot accidentally blur layer
  boundaries.

## ADR-006: Reject malformed values instead of silently coercing them

- **Status:** Accepted
- **Context:** Silent coercion can turn bad source values into plausible results.
- **Decision:** Collect stable, row-addressable validation issues and reject the
  dataset before normalization when blocking problems exist.
- **Consequences:** Users can repair multiple errors in one pass, and downstream
  code never receives partially valid data.

## ADR-007: Preserve raw inputs and normalize only in memory

- **Status:** Accepted
- **Context:** Source traceability requires byte-stable challenge inputs.
- **Decision:** Load strings strictly, validate them, then normalize a deep working
  copy without writing corrected source or normalized output files.
- **Consequences:** Raw files remain auditable; every later phase consumes a clean
  `InputBundle` rather than mutating source-backed frames.

## ADR-008: Treat the sample output header as authoritative

- **Status:** Accepted
- **Context:** Illustrative body rows contain natural-language commas that are not
  consistently quoted.
- **Decision:** Validate the first CSV record as the exact output contract and emit
  non-blocking diagnostics for inconsistent body field counts.
- **Consequences:** A malformed example does not invalidate the correct schema and
  is never silently repaired.

## ADR-009: Use strict ISO dates and derive Monday weeks

- **Status:** Accepted
- **Context:** Locale inference and inconsistent week starts undermine repeatability.
- **Decision:** Accept only valid `YYYY-MM-DD` values and derive `week_of` through
  weekday calendar arithmetic.
- **Consequences:** Dates are timezone-naive and every derived week begins Monday.

## ADR-010: Centralize CSV access through the ingestion service

- **Status:** Accepted
- **Context:** Scattered `read_csv` calls would duplicate rules and weaken the input
  boundary.
- **Decision:** Later phases obtain a validated `InputBundle` from
  `load_input_bundle`; dedicated loaders are the only canonical CSV readers.
- **Consequences:** File handling, validation, reports, and normalization remain
  independently testable and consistent.

## ADR-011: Aggregate numerator and denominator before division

- **Status:** Accepted
- **Context:** Averaging shipment-level rates gives small and large shipments equal
  influence and violates the mathematical contract.
- **Decision:** Sum freight cost and tonne-kilometres for each route, route type,
  and week, then divide the aggregated totals.
- **Consequences:** Weekly rates are correctly weighted by freight-distance.

## ADR-012: Retain weekly audit fields

- **Status:** Accepted
- **Context:** Every rate must be explainable and independently recalculable.
- **Decision:** Retain shipment count, total freight cost, total quantity, and total
  tonne-kilometres beside each calculated rate.
- **Consequences:** Reconciliation and later investigation can prove each result's
  numerator, denominator, and contributing volume.

## ADR-013: Keep canonical analytics numeric and unrounded

- **Status:** Accepted
- **Context:** Early rounding can change later baselines and anomaly boundaries.
- **Decision:** Preserve floating-point values at their available precision and
  defer formatting to export or presentation layers.
- **Consequences:** Tests use explicit tolerances and later phases receive the full
  calculated precision.

## ADR-014: Sort weekly metrics deterministically

- **Status:** Accepted
- **Context:** Reproducible downstream calculations require stable row and summation
  order independent of source ordering.
- **Decision:** Canonically order working rows by group key and shipment ID, then
  stably sort results by route, route type, and week with a reset index.
- **Consequences:** Shuffled logical inputs produce identical weekly tables.

## ADR-015: Keep analytics independent from I/O and API routes

- **Status:** Accepted
- **Context:** Calculation code should remain independently testable and reusable.
- **Decision:** The analytics service accepts only a normalized DataFrame. The
  inspection CLI composes ingestion and analytics without adding persistence.
- **Consequences:** No CSV access, HTTP concern, cache, or hidden write exists in
  the canonical calculation function.

## ADR-016: Shift before applying the history window

- **Status:** Accepted
- **Context:** Including the current week would leak the value being evaluated into
  its own comparison baseline.
- **Decision:** Shift each route and route-type cost series by one observation before
  applying the trailing eight-observation mean.
- **Consequences:** Only strictly earlier observations contribute to own history.

## ADR-017: Use available observations without padding

- **Status:** Accepted
- **Context:** Routes may have calendar weeks without shipments.
- **Decision:** Use up to eight prior observed route weeks and never synthesize,
  interpolate, or pad missing calendar weeks.
- **Consequences:** Audit counts state the actual amount of history used, including
  fewer than eight observations during early history.

## ADR-018: Average peer route-level rates without weighting

- **Status:** Accepted
- **Context:** The peer contract compares route-level weekly costs, not pooled
  shipment volumes.
- **Decision:** Calculate a simple arithmetic mean of eligible peer route rates.
- **Consequences:** Shipment count, quantity, and tonne-kilometres do not alter a
  peer route's influence.

## ADR-019: Exclude the current route from its peer baseline

- **Status:** Accepted
- **Context:** Self-inclusion would dilute route-specific differences.
- **Decision:** Subtract the current route rate and one route from each same-week,
  same-type peer group before calculating its average.
- **Consequences:** Two-route groups compare each route directly with the other;
  one-route groups have no available peer baseline.

## ADR-020: Represent unavailable baselines with missing values and counts

- **Status:** Accepted
- **Context:** Zero is a valid numeric value in comparisons but does not mean that a
  comparison source exists.
- **Decision:** Keep unavailable baselines as numeric missing values and record zero
  in the corresponding history or peer count.
- **Consequences:** Later phases can distinguish unavailable comparisons without
  guessing, strings, or sentinel numbers.
