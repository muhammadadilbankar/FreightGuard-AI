# FreightGuard AI - Master Implementation Roadmap

## 1. Project vision

FreightGuard AI is an evidence-first freight-cost anomaly investigation system. It calculates weekly route-level freight costs, detects unusual increases, searches contextual notes for possible explanations, validates whether the evidence genuinely applies, and produces an audit-ready CSV and interactive dashboard.

The system must prioritize correctness, reproducibility, and grounded reasoning over flashy AI output.

### Product promise

> Every flag comes with the math, every clearance comes with evidence, and every unsupported explanation is rejected.

## 2. Non-negotiable architecture

The solution is divided into independent layers:

1. Deterministic data ingestion and validation
2. Deterministic weekly cost analytics
3. Deterministic baseline and anomaly detection
4. Context-note normalization and retrieval
5. Rule-based evidence validation
6. Constrained explanation generation
7. Evaluation and reproducibility checks
8. FastAPI service layer
9. React investigation dashboard
10. Optional natural-language investigation assistant

An LLM must never calculate baselines, decide whether a row is anomalous, select the final matched note, or change the final verdict. AI may retrieve semantically relevant notes and generate wording from an already validated evidence packet.

## 3. Technology choices

| Area | Recommended technology | Reason |
|---|---|---|
| Analytics | Python and Pandas | Transparent and easy to test for this dataset size |
| API | FastAPI | Typed endpoints, validation, and automatic API documentation |
| Schemas | Pydantic | Strict input, output, and AI-response validation |
| Testing | Pytest | Unit, integration, regression, and reproducibility tests |
| Retrieval | Sentence Transformers with FAISS | Local semantic retrieval with no mandatory paid dependency |
| Frontend | React, Vite, Tailwind CSS | Fast development and a polished demo |
| Charts | Recharts | Route trend and baseline visualizations |
| Persistence | CSV and JSON initially | Keeps the analytical pipeline simple and reproducible |
| Optional cache | SQLite or file cache keyed by input hash | Faster repeated demos without changing canonical output |
| Packaging | Docker after local stability | Reproducible delivery without slowing early development |

## 4. Mathematical contract

### 4.1 Route identity

A route is directional and defined as:

```text
route = origin + "-" + destination
```

`Mumbai-Pune` and `Pune-Mumbai` must be treated as different routes if both exist.

### 4.2 Week assignment

Weeks run from Monday through Sunday. `week_of` is the Monday belonging to the shipment date.

### 4.3 Weekly cost per tonne-kilometre

For each `route + route_type + week_of` group:

```text
cost_per_tonne_km =
    sum(freight_cost_inr)
    / sum(quantity_tonnes * distance_km)
```

Do not calculate the mean of shipment-level ratios. Keep full numerical precision internally and round only when serializing user-facing output.

### 4.4 Own-history baseline

For route-week `t`:

- Use weekly cost values from the previous eight available weeks for that route.
- Exclude the current week.
- Never include future weeks.
- When fewer than eight previous weeks exist, use all available previous weeks.
- Do not pad, interpolate, or extrapolate missing history.

### 4.5 Similar-route baseline

For route-week `t`:

- Use other routes with the same `route_type` in the same week.
- Exclude the current route from its own peer average.
- Calculate the arithmetic mean of peer route-level weekly cost values.

### 4.6 Percentage deviations

```text
vs_own_history_pct =
    (current_cost / own_history_average - 1) * 100

vs_similar_routes_pct =
    (current_cost / similar_routes_average - 1) * 100
```

### 4.7 Default candidate anomaly rule

The challenge does not prescribe an anomaly threshold. The threshold must therefore be configurable and documented. The initial default is:

```text
candidate =
    vs_own_history_pct > 0
    AND
    (
        vs_own_history_pct >= 20
        OR vs_similar_routes_pct >= 20
    )
```

Do not hardcode specific routes, dates, note IDs, or known anomalous rows.

## 5. Output contract

The submission CSV must contain exactly these columns in this order:

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

Rules:

- Candidate anomalies remain in the output even when contextual evidence clears them.
- Use `Yes` for unexplained anomalies requiring review.
- Use `No (justified)` for candidates cleared by valid contextual evidence.
- Leave `matched_note_id` blank when no note fully justifies the anomaly.
- Use an RFC-compliant CSV writer so commas inside `reason` are correctly quoted.
- Sort rows deterministically by route and `week_of` before export.

## 6. Evidence contract

A context note may justify a candidate only if all required conditions pass:

1. The note applies to the exact route or explicitly to all routes.
2. The note's effective interval overlaps the candidate's week.
3. The note describes an increase-producing cause.
4. The note states or clearly implies that transport cost or rates were affected.
5. The note does not negate the cost impact.
6. The note's scope can explain the observed anomaly.

Examples of evidence that must be rejected:

- Correct topic but wrong route
- Correct route but wrong date
- Notes saying costs were not significantly affected
- Notes saying there was no rate change
- Notes reporting stable or normal operations
- Events affecting routes outside the dataset

A nationwide factor may explain part of an own-history increase but should not automatically clear a route-specific premium over equally exposed peers.

## 7. Implementation phases

## Phase 1 - Repository foundation

Create the project structure, backend environment, configuration, logging, FastAPI health endpoint, test setup, data directories, README, `.env.example`, and repository-wide development instructions.

### Completion gate

- Backend starts locally.
- `GET /health` returns a stable JSON response.
- Initial tests pass.
- Supplied input files remain byte-for-byte unmodified.
- No analytics, retrieval, AI, or frontend implementation exists yet.

## Phase 2 - Data ingestion and validation

Build strict loaders for shipment records, context notes, and the sample output contract.

Validate:

- Required columns
- Parseable dates
- Unique shipment IDs
- Valid route types
- Positive quantity, distance, and freight cost
- Non-empty route fields
- Missing and duplicate values

Create normalized fields such as `route`, `week_of`, and `tonne_km`.

### Completion gate

- Valid supplied input loads successfully.
- Malformed fixtures fail with clear validation errors.
- No source file is silently modified.

## Phase 3 - Weekly cost analytics

Aggregate shipment data by `route + route_type + week_of` and calculate weighted weekly cost per tonne-kilometre.

### Completion gate

- Supplied data produces 728 route-week records.
- Results cover seven routes and 104 weeks.
- Weighted aggregation tests pass.
- Internal calculations preserve full precision.

## Phase 4 - Baseline engine

Implement trailing own-history and same-week peer baselines exactly as defined by the challenge.

Store useful audit fields internally:

- `history_weeks_used`
- `peer_routes_used`
- History baseline value
- Peer baseline value

### Completion gate

- No current-week or future data leaks into history.
- Current route is excluded from peer calculations.
- Fewer-than-eight-week behaviour is tested.
- Supplied numerical examples match expected values within a declared tolerance.

## Phase 5 - Candidate detection and submission CSV

Implement configurable anomaly detection and generate the exact required output schema.

Before contextual intelligence exists, all candidates should remain unexplained and flagged.

### Completion gate

- Threshold is controlled from configuration.
- Boundary cases are tested.
- Column order and types are verified.
- Comma-containing explanations are correctly quoted.
- Output order is deterministic.

## Phase 6 - Context-note compiler

Normalize free-text context notes into structured evidence claims while preserving the original text.

Suggested internal fields:

```text
note_id
applies_to_routes
effective_from
effective_to
event_type
impact_direction
affects_transport_cost
magnitude_text
original_text
```

### Completion gate

- Every supplied note has a traceable structured representation.
- Negative and no-impact notes are represented correctly.
- Original note text remains unchanged and available for citation.

## Phase 7 - Hybrid retrieval and Evidence Gate

Implement semantic retrieval plus strict route, date, direction, impact, and scope validation.

Possible verdicts:

```text
justified
unexplained
partially_explained
```

The evidence gate owns the final verdict and matched note ID.

### Completion gate

- Wrong-route, wrong-date, and no-impact notes are rejected.
- Valid evidence is accepted.
- Missing evidence produces `unexplained` rather than a guessed reason.
- Global events do not incorrectly erase route-specific peer anomalies.

## Phase 8 - Grounded explanation generation

Introduce a provider-independent explanation interface. The generator receives only a validated evidence packet and cannot alter calculations or verdicts.

Requirements:

- Temperature zero where supported
- Structured model response
- Pydantic validation
- Permitted note-ID allowlist
- Deterministic fallback templates
- Token, call-count, and estimated-cost logging

### Completion gate

- Generated explanations cannot introduce an unapproved note ID.
- Validation failures fall back safely.
- Re-running generation cannot change canonical numbers, note IDs, or verdicts.

## Phase 9 - Evaluation and reproducibility harness

Create automated evaluation commands covering mathematical correctness, evidence validity, output format, and three-run reproducibility.

Include labelled adversarial cases for:

- Wrong route
- Wrong date
- Negated cost impact
- Normal-operation note
- No evidence
- Partially relevant nationwide event

### Completion gate

- Three untouched runs produce byte-identical canonical CSV output.
- SHA-256 hashes are recorded.
- Numerical regression tests pass.
- Evaluation report is generated in a human-readable format.

## Phase 10 - FastAPI service layer

Expose the stable analytical pipeline through thin API routes.

Suggested endpoints:

```text
GET  /health
POST /api/analysis/run
GET  /api/analysis/summary
GET  /api/anomalies
GET  /api/anomalies/{route}/{week_of}
GET  /api/routes/{route}/timeline
GET  /api/evaluation/report
GET  /api/run-metrics
```

### Completion gate

- API routes delegate to services rather than duplicating business logic.
- Schemas are documented automatically.
- Invalid requests produce clear errors.
- API integration tests pass.

## Phase 11 - React investigation dashboard

Build the demo interface in this order:

1. Overview metrics
2. Investigation queue
3. Route trend chart
4. Cost Courtroom evidence drawer
5. Evidence validation checklist
6. CSV export and run-metrics panel

### Completion gate

- A judge can identify the most important anomaly within seconds.
- Every verdict can be traced to its math and evidence.
- Loading, empty, and error states work.
- No calculations are duplicated in the frontend.

## Phase 12 - Operational root-cause analysis

For unexplained anomalies, analyse transporter mix, material mix, shipment count, average load, distance variation, and transporter-level pricing changes.

This layer provides investigative leads but cannot clear an anomaly under the context-note evidence contract.

### Completion gate

- Contribution calculations are documented and tested.
- UI clearly separates operational clues from accepted contextual evidence.
- Root-cause suggestions never modify canonical verdicts.

## Phase 13 - Natural-language investigation assistant

Allow users to ask questions about computed findings and context evidence.

Example questions:

- Why did Chennai-Bangalore become expensive in March?
- Which unexplained route had the largest peer deviation?
- Show Mumbai-Pune anomalies after September.
- Which retrieved notes failed the Evidence Gate?

### Completion gate

- Answers are grounded in stored analytical results.
- Route, week, and note identifiers are cited.
- Unsupported questions receive an honest limitation response.
- Chat cannot change or override canonical results.

## Phase 14 - Packaging, documentation, and demo hardening

Finalize:

- README
- Architecture diagram
- Methodology and trade-offs
- Reproducibility report
- Token and cost report
- Example output CSV
- Optional Docker setup
- Ten-minute walkthrough script
- Backup demo data and cached results

### Completion gate

- A clean-machine setup is documented.
- Local demo works without relying on a fragile external service.
- Submission files match the challenge requirements.
- The ten-minute walkthrough has been rehearsed against the final build.

## 8. Development workflow for every phase

For each phase, Codex must:

1. Read `AGENTS.md` and the project documents.
2. Inspect existing code before editing.
3. State the intended changes briefly.
4. Implement only the requested phase.
5. Add focused tests.
6. Run tests with sensible timeouts.
7. Run formatting or linting if configured.
8. Provide manual verification commands.
9. Update the phase checklist.
10. Suggest one Git commit message.
11. Stop before beginning the next phase.

## 9. Definition of done for the complete project

The project is complete only when:

- Core numerical calculations match the challenge definitions.
- Context verdicts survive route, time, impact, and scope checks.
- Unsupported anomalies remain unexplained.
- Required CSV columns, order, and types are correct.
- Three runs produce identical canonical output.
- Token and cost usage is reported honestly.
- Tests and evaluation commands pass.
- The dashboard makes every decision auditable.
- The README and walkthrough explain the engineering trade-offs clearly.

