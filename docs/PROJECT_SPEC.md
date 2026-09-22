# FreightGuard AI project specification

## Business problem and product principles

FreightGuard AI identifies unusual weekly freight-cost increases and helps an
investigator decide whether contemporaneous context genuinely explains them. The
system is evidence-first: every flag exposes its mathematics, every clearance cites
validated evidence, and unsupported explanations are rejected. Correctness,
reproducibility, traceability, and deterministic decisions take precedence over
fluent AI output.

## Inputs and required output

Canonical inputs are unchanged copies of:

- `shipment_records.csv`
- `context_notes.csv`
- `sample_output_format_v2.csv`

The final CSV columns, in order, are `route`, `week_of`,
`cost_per_tonne_km`, `vs_own_history`, `vs_similar_routes`, `flagged`,
`matched_note_id`, and `reason`. Rows are sorted by route and week. Candidates
remain present after justification; `flagged` is `Yes` when unexplained and
`No (justified)` when cleared. A note ID is blank unless evidence fully justifies
the anomaly.

## Mathematical contract

- A directional route is `origin + "-" + destination`.
- Weeks run Monday through Sunday; `week_of` is the Monday for a shipment date.
- For each route, route type, and week, cost per tonne-kilometre is
  `sum(freight_cost_inr) / sum(quantity_tonnes * distance_km)`. It is never the
  mean of shipment-level ratios.
- The own-history baseline is the arithmetic mean of the prior eight available
  route weeks, excluding current and future weeks. Use all prior weeks when fewer
  than eight exist; never pad missing history.
- The peer baseline is the arithmetic mean of other routes' route-level costs for
  the same route type and week. The current route is excluded.
- Percentage deviation is `(current / baseline - 1) * 100`.
- Preserve full internal precision and round only serialized user-facing values.

## Candidate rule

The configurable initial rule is:

```text
vs_own_history_pct > 0 AND
(vs_own_history_pct >= 20 OR vs_similar_routes_pct >= 20)
```

## Evidence validation

A note can justify a candidate only when its route (or explicit all-route scope),
effective interval, increase direction, transport-cost impact, lack of negation,
and explanatory scope all pass validation. Reject wrong-route, wrong-date,
no-impact, no-rate-change, stable-operation, and out-of-dataset evidence. A global
factor does not automatically clear a route-specific premium over equally exposed
peers. Only deterministic rules own the verdict and matched note ID.

## Reproducibility

Canonical CSV output must be byte-identical across three untouched runs, with
SHA-256 hashes recorded. Evaluation covers numerical correctness, evidence
validity, output format, adversarial notes, and reproducibility. AI may retrieve
context or phrase a validated evidence packet, but cannot change calculations,
evidence selection, identifiers, or verdicts.
