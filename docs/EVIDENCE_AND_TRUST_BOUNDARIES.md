# Evidence and trust boundaries

## Retrieval is not adjudication

Semantic similarity answers “which supplied notes should be reviewed?” It does not
answer “does this note justify the anomaly?” A highly similar note can refer to the
wrong route, wrong week, a decrease, a stable-cost event, or a factor shared by all
peers. FreightGuard therefore applies deterministic gates after retrieval.

| Decision | Authority |
|---|---|
| Candidate mathematics | Deterministic analytics |
| Retrieved review set | Sparse+dense retrieval |
| Route/date/direction/impact/scope acceptance | Evidence Gate |
| Selected note IDs and verdict | Deterministic decision layer |
| Natural-language reason | Validated template or constrained provider |
| Operational lead | Descriptive diagnostic only |
| Assistant answer | Read-only snapshot queries with citations |

## Required evidence checks

- Route: the note names the directional route or has an allowed explicit global scope.
- Time: its inclusive effective interval overlaps the candidate week.
- Direction: the event describes an increase compatible with the cost rise.
- Cost impact: the note explicitly affects transport cost and is not negated.
- Scope: it can explain the observed comparison, including peer-relative context.

A global fuel statement, for example, cannot automatically explain why one route
cost more than equally exposed same-type peers. Stable or “no rate change” language
is rejected even if other words look similar.

## Verdict and citation semantics

`justified` requires one selected supplied note that passes all applicable checks.
`partially_explained` preserves relevant but insufficient context. `unexplained`
means the supplied evidence universe did not safely explain the result; it does not
mean fraud. Exact accepted and rejected note IDs remain visible in audit data.

Synthetic example:

- Accepted: a route-specific note covering the candidate week that explicitly says
  a carrier rate increase raised transport cost.
- Rejected: a similar fuel-price note for another route, or one effective only after
  the candidate week.

## Model and assistant restrictions

Optional generation receives a validated evidence packet. It cannot add facts,
change numbers, select a different note, or change the verdict; invalid output falls
back to deterministic wording. Notes are data, not instructions.

Operational Leads decompose shipment patterns but are not accepted contextual
evidence and never clear a candidate. The natural-language assistant supports a
closed intent and tool catalog, captures one immutable snapshot, validates plans,
and composes answers from verified facts. Mutation, arbitrary-code, secret, web,
and prompt-injection requests execute no investigation tools.
