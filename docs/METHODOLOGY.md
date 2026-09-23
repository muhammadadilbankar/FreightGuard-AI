# Methodology

## Route and week identity

A route is directional: `origin + "-" + destination`. The implementation uses the
supplied `route_type`; it does not invent distance buckets. Shipment dates are
assigned to Monday-through-Sunday weeks, with `week_of` equal to Monday.

Code: `services/ingestion/normalization.py` and
`services/analytics/weekly_cost.py`. Tests: `test_normalization.py` and
`test_weekly_cost.py`.

## Weighted weekly cost

```text
cost_per_tonne_km =
    sum(freight_cost_inr)
    / sum(quantity_tonnes * distance_km)
```

The numerator is INR and the denominator is tonne-km. This is not the mean of
shipment-level ratios. Zero or invalid physical quantities fail validation. Full
precision is retained internally; rounding occurs only in serialized output.

## Own-history baseline

For each route, the baseline is the arithmetic mean of the previous eight available
route-week costs, strictly before the current week. With fewer than eight prior
observations, every available observation is used. The implementation never pads,
interpolates, calendar-fills, extrapolates, or looks ahead.

Code: `services/analytics/baselines.py`. Tests: `test_baselines.py` and
`test_baselines_supplied_data.py`.

## Similar-route baseline

Peers are other routes in the same supplied `route_type` and the same week. The
current route is excluded, then the arithmetic mean of peer route-week costs is
used. No available peers means no peer comparison rather than a fabricated zero.

## Deviations and candidate rule

```text
deviation_pct = (current_cost / baseline - 1) * 100

candidate = own_deviation > 0 and
            (own_deviation >= threshold or peer_deviation >= threshold)
```

The threshold defaults to 20%, because the brief does not prescribe one, and is
exposed as `ANOMALY_THRESHOLD_PERCENT`. Comparisons use unrounded values; the CSV
formats user-facing percentages later. Non-finite values are rejected.

Code: `comparisons.py` and `candidates.py`. Tests: comparison, candidate, and
metamorphic evaluation suites.

## Context intelligence

Notes are compiled into typed route scope, effective interval, event type,
direction, transport-cost impact, and magnitude fields. Sparse and local dense
retrieval create a review set. The Evidence Gate then checks route applicability,
date overlap, increase direction, positive transport-cost impact, negation, and
explanatory scope. Retrieval score is never an acceptance rule.

Verdicts mean:

- `justified`: selected evidence fully explains the candidate under every gate.
- `partially_explained`: relevant context exists but does not fully justify it.
- `unexplained`: no supplied context safely explains it.

## Output mapping

All candidate rows remain in the supplied eight-column schema. Fully justified
rows serialize as `No (justified)` with the selected note ID. Other candidates stay
flagged and have a blank `matched_note_id`. The reason is built from the canonical
decision packet and cannot introduce a different note, number, or verdict.

The complete contract and edge cases are exercised by the unit tests under
`backend/tests/unit/`, supplied-data integration tests, negative controls, and the
formal evaluation mathematics/output domains.
