# FreightGuard AI - Phase 7 Hybrid Retrieval and Evidence Gate Implementation Plan

## 1. Purpose of this document

This document is the complete implementation contract for Phase 7 of FreightGuard AI. Give it to Codex only after Phases 1 through 6 have been completed, tested, and committed.

Phase 7 connects the 19 Phase 5 candidate anomalies with the typed context claims produced by Phase 6. It uses hybrid retrieval to find potentially relevant notes, then applies a deterministic Evidence Gate that independently validates route, date, direction, transport-cost impact, negation, and explanatory scope.

The retrieval layer may propose evidence. It must never decide the verdict. The Evidence Gate is the only component allowed to classify a candidate as `justified`, `partially_explained`, or `unexplained`, and the only component allowed to select the final `matched_note_id`.

Phase 7 produces deterministic evidence decisions, an auditable candidate-note trace, and an evidence-reviewed eight-column CSV. It does not generate LLM-written explanations; Phase 8 owns that work.

## 2. Phase objective

Build an evidence-review pipeline that:

- Consumes canonical Phase 5 candidate metrics, not formatted CSV strings.
- Consumes validated Phase 6 `CompiledContextNote` models.
- Constructs deterministic candidate investigation queries.
- Retrieves notes through sparse lexical and dense semantic channels.
- Fuses retrieval ranks without depending on incomparable raw-score scales.
- Adds a structured-recall safety net based on route and time metadata.
- Records why every evaluated candidate-note pair passed or failed.
- Rejects wrong-route, wrong-date, outside-dataset, negated, no-impact, and normal-operation notes.
- Distinguishes full justification from partial explanation.
- Prevents nationwide events from clearing route-specific peer anomalies.
- Selects at most one final matched note by deterministic policy.
- Keeps all 19 Phase 5 candidates in the reviewed output.
- Maps internal verdicts to the exact challenge output contract.
- Produces a deterministic audit JSONL and evidence-reviewed CSV.
- Exposes a CLI that runs Phases 2 through 7 end to end.
- Adds unit, adversarial, integration, reproducibility, and supplied-data regression tests.

## 3. Preconditions

Before editing, Codex must verify:

- All Phase 1 through Phase 6 tests pass.
- Phase 5 evaluates 728 route-week rows and detects exactly 19 candidates with the default 20% threshold.
- Phase 5 candidate metrics retain the full-precision internal columns required by the gate.
- Phase 6 compiles exactly 10 source notes into typed models.
- Every compiled note preserves its original text and source identity.
- The Phase 6 supplied-data regression contract passes.
- The embedding model configuration exists and is not loaded during application import.
- Generated output paths are ignored by Git unless fixtures are intentionally tracked.
- Original challenge inputs remain unchanged.
- The Git working tree is inspected and unrelated changes are preserved.

If equivalent interfaces use different names, adapt to the existing architecture without rewriting correct prior-phase logic. Report all material deviations.

## 4. Non-negotiable trust boundary

The system must preserve this control flow:

```text
Candidate metrics
      |
      v
Hybrid retrieval ---------> candidate note suggestions
      |                              |
      +------------------------------+
                                     v
                         Deterministic Evidence Gate
                                     |
                                     v
                    verdict + selected evidence + audit
```

Rules:

- Similarity is a discovery signal, never proof.
- A high retrieval score cannot bypass a failed gate.
- A low retrieval score cannot invalidate structurally valid evidence discovered by the recall safety net.
- An embedding model cannot set `flagged`, `matched_note_id`, or `verdict`.
- No LLM may participate in the gate.
- Phase 8 may improve explanation wording, but it cannot change Phase 7 numbers, verdicts, or selected note IDs.

## 5. Phase boundary

### Phase 7 owns

- Candidate investigation-query construction.
- Sparse retrieval.
- Local dense semantic retrieval.
- Deterministic rank fusion.
- Structured route/time recall.
- Candidate-note gate assessments.
- Full, partial, and rejected evidence classification.
- Final candidate verdict.
- Deterministic selected-note policy.
- Internal supporting note IDs for partial explanations.
- Evidence audit artifact.
- Evidence-reviewed CSV with deterministic template reasons.

### Phase 7 does not own

- Weekly cost calculations.
- Baseline calculations.
- Candidate threshold decisions.
- Raw note parsing or semantic compilation.
- Rewriting Phase 6 structured claims.
- LLM calls or prompt templates.
- Generative explanation wording.
- Token or model-API cost accounting.
- API endpoints, frontend work, databases, or deployment.
- Deleting a candidate because evidence justifies it.

## 6. Canonical inputs

### 6.1 Candidate input

Consume the canonical Phase 5 comparison-and-candidate DataFrame, filtered to:

```text
candidate_anomaly == True
```

Required internal fields:

```text
route
route_type
week_of
cost_per_tonne_km
own_history_avg_cost_per_tonne_km
similar_routes_avg_cost_per_tonne_km
vs_own_history_pct
vs_similar_routes_pct
is_rising
own_threshold_breached
peer_threshold_breached
candidate_anomaly
```

Requirements:

- Values remain full precision.
- Candidate keys are unique.
- `week_of` is a Monday.
- Candidate week is the inclusive interval `week_of` through `week_of + 6 days`.
- Rule booleans are non-null.
- Phase 7 must not recompute or reinterpret candidate status.

### 6.2 Compiled-note input

Consume Phase 6 typed models directly. Required fields include:

```text
note_id
scope_type
scope_status
applies_to_routes
effective_from
effective_to
event_type
impact_direction
cost_impact_status
affects_transport_cost
negates_cost_increase
magnitude_text
original_text
compilation_warnings
```

Do not reparse the raw CSV. Do not reconstruct Phase 6 fields from `original_text` inside the Evidence Gate.

## 7. Core domain contracts

Define immutable typed models equivalent to the following.

### 7.1 Candidate evidence query

```python
class CandidateEvidenceQuery(BaseModel):
    route: str
    route_type: str
    week_of: date
    week_end: date
    cost_per_tonne_km: float
    vs_own_history_pct: float
    vs_similar_routes_pct: float | None
    own_threshold_breached: bool
    peer_threshold_breached: bool
    query_text: str
```

### 7.2 Retrieval hit

```python
class RetrievalHit(BaseModel):
    note_id: str
    sparse_rank: int | None
    sparse_score: float | None
    dense_rank: int | None
    dense_score: float | None
    fused_rank: int | None
    fused_score: float | None
    included_by_structured_recall: bool
```

### 7.3 Gate assessment

```python
class EvidenceAssessment(BaseModel):
    route: str
    week_of: date
    note_id: str
    route_check: GateCheck
    date_check: GateCheck
    scope_check: GateCheck
    direction_check: GateCheck
    cost_impact_check: GateCheck
    negation_check: GateCheck
    explanatory_scope: EvidenceCoverage
    overlap_days: int
    evidence_level: EvidenceLevel
    rejection_codes: tuple[RejectionCode, ...]
    retrieval: RetrievalHit
```

### 7.4 Candidate evidence decision

```python
class EvidenceDecision(BaseModel):
    route: str
    week_of: date
    verdict: EvidenceVerdict
    selected_note_id: str | None
    supporting_note_ids: tuple[str, ...]
    reason_template_key: ReasonTemplateKey
    assessed_note_ids: tuple[str, ...]
```

### 7.5 Validated evidence packet

Create a Phase 8-ready immutable packet:

```python
class ValidatedEvidencePacket(BaseModel):
    candidate: CandidateEvidenceSummary
    decision: EvidenceDecision
    selected_note: CompiledContextNote | None
    supporting_notes: tuple[CompiledContextNote, ...]
    allowed_note_ids: tuple[str, ...]
```

`allowed_note_ids` must equal the selected full-evidence note plus any accepted partial-support notes. Rejected note IDs must never appear in this allowlist.

## 8. Enumerations

### 8.1 Gate check

```text
pass
fail
not_applicable
```

### 8.2 Evidence coverage

```text
full
partial
none
```

### 8.3 Evidence level

```text
full
partial
rejected
```

### 8.4 Final verdict

```text
justified
partially_explained
unexplained
```

### 8.5 Rejection codes

At minimum support:

```text
scope_outside_dataset
scope_unresolved
route_mismatch
date_no_overlap
cost_impact_not_positive
impact_direction_not_increase
cost_increase_negated
global_scope_cannot_explain_peer_premium
compiled_claim_inconsistent
```

Codes are stable, deduplicated, and lexicographically sorted in serialized output.

## 9. Folder and module structure

Extend the established backend cleanly:

```text
backend/
├── app/
│   ├── domain/
│   │   └── evidence.py
│   └── services/
│       ├── evidence/
│       │   ├── __init__.py
│       │   ├── decisions.py
│       │   ├── gate.py
│       │   ├── hybrid.py
│       │   ├── queries.py
│       │   ├── recall.py
│       │   └── retrieval_documents.py
│       ├── retrieval/
│       │   ├── __init__.py
│       │   ├── dense.py
│       │   ├── embeddings.py
│       │   └── sparse.py
│       └── reporting/
│           ├── evidence_audit.py
│           └── evidence_csv.py
├── scripts/
│   ├── prepare_embedding_model.py
│   └── review_candidate_evidence.py
└── tests/
    ├── fixtures/
    │   └── evidence/
    │       ├── adversarial_evidence_cases.json
    │       └── expected_supplied_decisions.jsonl
    ├── unit/
    │   ├── evidence/
    │   │   ├── test_decisions.py
    │   │   ├── test_evidence_gate.py
    │   │   ├── test_hybrid_retrieval.py
    │   │   ├── test_queries.py
    │   │   └── test_structured_recall.py
    │   └── retrieval/
    │       ├── test_dense_retrieval.py
    │       └── test_sparse_retrieval.py
    └── integration/
        ├── test_evidence_pipeline_supplied_data.py
        └── test_evidence_outputs.py
```

Responsibilities:

- `domain/evidence.py`: typed evidence contracts and enums.
- `queries.py`: deterministic candidate query text.
- `retrieval_documents.py`: deterministic searchable note representation.
- `sparse.py`: TF-IDF lexical retrieval.
- `embeddings.py`: embedding-provider protocol and local provider adapter.
- `dense.py`: dense similarity ranking over in-memory note vectors.
- `hybrid.py`: Reciprocal Rank Fusion and deterministic tie-breaking.
- `recall.py`: structured route/time candidate generation.
- `gate.py`: hard evidence checks for one candidate-note pair.
- `decisions.py`: aggregate assessments into a final verdict and selected note.
- `evidence_audit.py`: deterministic audit JSONL.
- `evidence_csv.py`: map evidence decisions to the exact eight-column output.
- `review_candidate_evidence.py`: thin end-to-end orchestration.

Equivalent names are acceptable when consistent with the repository. Do not combine retrieval, gate rules, decisions, formatting, and CLI logic in one file.

## 10. Configuration contract

Add focused settings equivalent to:

```dotenv
RETRIEVAL_TOP_K=5
RETRIEVAL_RRF_K=60
RETRIEVAL_SPARSE_WEIGHT=1.0
RETRIEVAL_DENSE_WEIGHT=1.0
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_MODEL_REVISION=<pinned-tested-revision>
EMBEDDING_MODEL_PATH=
EMBEDDING_LOCAL_ONLY=true
GLOBAL_MAGNITUDE_TOLERANCE_PERCENT=2.0
```

Requirements:

- `top_k` is a positive integer and cannot exceed note count after clamping.
- `rrf_k` is a positive integer.
- Retrieval weights are finite and non-negative, with at least one positive.
- Model name/path/revision are validated once at the boundary.
- Production and demo runs must pin an exact model revision or use a versioned local model directory.
- Tests must never download a model or call an external API.
- `local_only=true` must fail clearly when model files are missing.
- The model is loaded lazily only when semantic retrieval runs.
- No embedding model setting may affect hard gate semantics.

The repository should pin compatible Python package versions in its existing dependency mechanism after testing them together. Do not add floating, unbounded dependencies.

## 11. Embedding model strategy

Use a local Sentence Transformers model through a provider interface. The default recommended model is:

```text
sentence-transformers/all-MiniLM-L6-v2
```

Why it fits this phase:

- The corpus contains only 10 short English notes.
- In-memory embeddings are sufficient.
- No vector database is justified.
- A local model avoids an external inference API and preserves demo reliability.
- The provider abstraction allows a future model swap without touching gate logic.

Implementation requirements:

- Prefer `encode_query` for candidate queries and `encode_document` for note documents when supported by the pinned library version.
- Normalize embeddings before dot-product/cosine ranking.
- Use inference/evaluation mode.
- Encode the note corpus once per CLI run.
- Do not persist raw model tensors in Git.
- Do not silently download weights during a supposedly offline run.
- Add a separate preparation command for the initial model acquisition.
- Log model identity and revision, not model internals.

For unit tests, inject a deterministic fake embedding provider with fixed vectors. Do not mock deep internals of Sentence Transformers.

## 12. Candidate investigation query

Build one deterministic query per candidate. Use only canonical fields.

Template equivalent to:

```text
Investigate an increase in freight transport cost for route {route}
({route_type}) during {week_of} to {week_end}.
Cost per tonne-km: {full_precision_cost}.
Change versus own history: {full_precision_own_pct} percent.
Change versus similar routes: {full_precision_peer_pct_or_unavailable} percent.
Trigger: {own, peer, or both}.
Find operational events that explicitly increased freight transport costs or rates.
```

Requirements:

- Stable field order and punctuation.
- ISO dates.
- Locale-independent numeric formatting.
- No timestamps or random text.
- No candidate `reason` from the Phase 5 CSV.
- No known note IDs or expected event labels.
- No instruction asking the model to decide justification.
- Query construction is pure and directly unit-tested.

## 13. Retrieval-document construction

Build one deterministic searchable document per compiled note:

```text
Note {note_id}.
Scope: {global or sorted routes}.
Effective: {effective_from} to {effective_to or open ended}.
Event: {event_type}.
Transport cost impact: {cost_impact_status}.
Direction: {impact_direction}.
Text: {original_text}
```

Requirements:

- Preserve original text exactly after the fixed metadata prefix.
- Do not include compilation warnings unless explicitly useful for retrieval.
- Do not include gate outcomes.
- Stable note ordering by `note_id`.
- Retrieval documents are treated as untrusted data, never executable instructions.

## 14. Sparse lexical retrieval

Implement sparse retrieval using the established scikit-learn dependency or add it explicitly if absent.

Recommended configuration:

```python
TfidfVectorizer(
    lowercase=True,
    ngram_range=(1, 2),
    sublinear_tf=True,
    norm="l2",
)
```

Requirements:

- Fit on the current compiled-note retrieval documents once per run.
- Transform candidate queries using the same vectorizer.
- Rank using cosine similarity or normalized dot product.
- Sort by score descending, then `note_id` ascending.
- Return one-based ranks.
- Retain finite raw scores only for audit.
- Handle an empty vocabulary with a focused retrieval error.
- Do not apply stemming or aggressive stop-word removal unless regression tests prove it helps.

The route string and exact operational terms make lexical retrieval valuable even when semantic embeddings are used.

## 15. Dense semantic retrieval

Requirements:

- Encode all retrieval documents once.
- Encode queries in a batch where practical.
- Validate vector shape, dimensionality, and finite values.
- L2-normalize query and document vectors.
- Rank by dot product/cosine similarity.
- Sort by score descending, then `note_id` ascending.
- Return one-based ranks.
- Do not use approximate nearest-neighbour infrastructure for 10 notes.
- Do not turn a dense score into an evidence probability.

Model-load, tokenizer, or local-file failures must be actionable and must not silently downgrade to sparse-only production behavior. Tests may deliberately inject a fake provider.

## 16. Reciprocal Rank Fusion

Fuse sparse and dense ranks using weighted Reciprocal Rank Fusion:

```text
fused_score(note) =
    sparse_weight / (rrf_k + sparse_rank)
    +
    dense_weight / (rrf_k + dense_rank)
```

Rules:

- Ranks are one-based.
- A missing channel rank contributes zero.
- Default `rrf_k = 60`.
- Default sparse and dense weights are equal.
- Sort by fused score descending, then best individual rank, then `note_id`.
- Return the configured top `k` notes.
- Preserve component ranks and scores for audit.
- Do not threshold the fused score as though it were calibrated confidence.

Rank fusion is chosen because lexical and dense score scales are not directly comparable.

## 17. Structured-recall safety net

Hybrid ranking must not be the only path by which a valid note reaches the gate.

For every candidate, independently include all compiled notes that satisfy the cheap structural recall predicate:

```text
scope is global or contains the exact candidate route
AND
the note interval overlaps the candidate week
```

Important:

- Do not filter on positive cost impact during recall; rejected no-impact notes are valuable audit cases.
- Do not filter out `outside_dataset` here; the gate must record that failure.
- Union structured-recall notes with the hybrid top-k notes.
- Deduplicate by `note_id`.
- Mark `included_by_structured_recall` in retrieval metadata.
- Evaluate the union in deterministic `note_id` order.

This creates a strong engineering guarantee: retrieval improves discovery and ranking, while exact structured facts protect recall for valid route/time evidence.

## 18. Evidence Gate order

Evaluate checks in a stable sequence for every candidate-note pair. Record all applicable failures rather than stopping at the first failure, unless a malformed compiled claim makes further evaluation unsafe.

### Gate 1: compiled-claim consistency

Revalidate critical Phase 6 invariants defensively:

- Effective end is not before start.
- Positive cost status agrees with direction and nullable Boolean.
- Negated claims are not marked as explicit increases.
- Route-scope shape is valid.

Inconsistent claims receive `compiled_claim_inconsistent` and cannot become evidence.

### Gate 2: dataset scope

Pass only when:

```text
scope_status in {in_dataset, partially_in_dataset}
```

Reject `outside_dataset` and `unresolved` with distinct codes.

### Gate 3: route applicability

Pass when either:

- `scope_type == global`, or
- Candidate route exactly equals one of `applies_to_routes`.

No fuzzy, substring, origin-only, destination-only, or reverse-direction match is allowed.

### Gate 4: date overlap

Candidate interval:

```text
[week_of, week_of + 6 days]
```

Note interval:

```text
[effective_from, effective_to]
```

Treat null `effective_to` as open-ended.

Overlap rule:

```text
note_start <= candidate_end
AND
(note_end is null OR note_end >= candidate_start)
```

Any one-day overlap passes the date gate. Store the exact inclusive overlap-day count.

### Gate 5: explicit positive transport-cost impact

Full or partial positive evidence requires all of:

```text
cost_impact_status in {explicit_increase}
affects_transport_cost is true
impact_direction == increase
```

Reject `not_stated`, `unknown`, explicit no-impact, no-rate-change, and normal/stable statuses.

### Gate 6: negation

Require:

```text
negates_cost_increase == false
```

An event-specific no-impact note rejects only itself. It must not cancel a separate valid note about a different event.

### Gate 7: explanatory scope

Determine whether otherwise-valid evidence can explain the candidate’s actual anomaly shape.

#### Exact route evidence

An exact route-specific note that passes all earlier gates receives `full` explanatory coverage. It can explain own-history, peer, or combined candidate triggers because the cause is specific to that route.

#### Global evidence with no peer breach

A global positive-cost note may receive `full` coverage only when:

- `peer_threshold_breached == false`, and
- The note can plausibly explain the own-history rise under the magnitude policy.

#### Global evidence with a peer breach

When `peer_threshold_breached == true`, global evidence receives at most `partial` coverage.

Reason: peer routes in the same week are expected to share a nationwide factor. A global event may contribute to the candidate’s own-history rise but cannot explain why the route remains unusually expensive relative to equally exposed peers.

Add `global_scope_cannot_explain_peer_premium` as a coverage limitation. It is not a rejection of the note’s partial relevance.

## 19. Magnitude plausibility policy

Magnitude never creates positive evidence. It only limits whether otherwise-valid global evidence can fully explain an own-history-only candidate.

Rules:

- Route-specific evidence does not require a numeric magnitude for full coverage.
- Global evidence with no numeric magnitude may still receive full coverage for an own-only anomaly when all hard gates pass.
- If global evidence contains a parsed percentage range, compare the full-precision own-history rise to the upper bound plus the configured tolerance.
- If the observed rise exceeds that bound, downgrade global evidence from full to partial.
- Never average a range.
- Never compare a percentage magnitude to peer deviation to justify a route-specific premium.
- Conflicting or unparseable magnitude remains non-authoritative and must not be invented.

Default tolerance:

```text
2.0 percentage points
```

This tolerance is configurable and must be documented. It is not used by the supplied-data full-justification cases, which rely on exact route evidence.

## 20. Evidence-level assignment

For each assessment:

```text
rejected
    if any hard gate fails

full
    if all hard gates pass and explanatory_scope == full

partial
    if all hard gates pass and explanatory_scope == partial
```

Hard gates are compiled consistency, dataset scope, route, date, positive cost impact, direction, and negation.

Multiple partial notes must not be combined mathematically into a full explanation during Phase 7. Additive causal reasoning belongs outside this deterministic scope unless a future specification defines it explicitly.

## 21. Final verdict policy

Aggregate all assessments for one candidate:

```text
justified
    if at least one full evidence assessment exists

partially_explained
    if no full evidence exists and at least one partial assessment exists

unexplained
    if neither full nor partial evidence exists
```

Requirements:

- Every candidate receives exactly one verdict.
- No non-candidate enters the decision set.
- A candidate is never deleted.
- Missing evidence produces `unexplained`, never a guessed justification.
- Rejected notes remain in the audit trace but not in `supporting_note_ids`.

## 22. Deterministic evidence selection

When multiple full notes exist, select exactly one `selected_note_id` using this order:

1. Exact route scope before global scope.
2. Larger inclusive date overlap.
3. Explicit numeric magnitude before no magnitude.
4. Better fused rank.
5. Better dense rank.
6. Better sparse rank.
7. Lexicographically smaller `note_id`.

Missing retrieval ranks sort after present ranks.

For partial decisions:

- `selected_note_id` remains null.
- Store every accepted partial note in sorted `supporting_note_ids`.
- The challenge `matched_note_id` remains blank because no note fully justifies the anomaly.

For unexplained decisions:

- `selected_note_id` is null.
- `supporting_note_ids` is empty.

This preserves the master output rule: populate `matched_note_id` only when a note fully justifies the candidate.

## 23. Deterministic reason templates

Phase 7 must use templates, not an LLM.

### Justified

```text
Valid context evidence {note_id} applies to this route and week and explicitly supports a transport-cost increase.
```

### Partially explained

```text
Context note {note_id} may explain the own-history rise, but its all-routes scope does not explain the route-specific peer premium.
```

When multiple partial notes exist, use the highest-priority supporting note for the display template while retaining all supporting IDs internally.

### Unexplained

```text
No context note passed all route, date, direction, cost-impact, and scope checks.
```

These reasons are safe fallbacks and Phase 8 inputs. Phase 8 may replace the wording but must not alter the verdict or selected note ID.

## 24. Mapping verdicts to the challenge output

The reviewed CSV retains exactly the eight authoritative columns:

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

Mapping:

| Internal verdict | `flagged` | `matched_note_id` |
|---|---|---|
| `justified` | `No (justified)` | Selected full-evidence note ID |
| `partially_explained` | `Yes` | Blank |
| `unexplained` | `Yes` | Blank |

Requirements:

- Retain all Phase 5 candidate rows.
- Do not add non-candidates.
- Preserve Phase 5 numerical display formatting.
- Preserve deterministic route/week ordering.
- Reuse the Phase 5 RFC-safe CSV writer and validator where possible.
- Do not duplicate formatting rules.
- Name the file `evidence_reviewed_anomalies.csv`.
- Do not call it `final_submission.csv`; Phase 8 still owns final explanation generation.

## 25. Evidence audit JSONL

Write:

```text
backend/data/output/evidence_gate_audit.jsonl
```

Use one candidate-level object per line containing:

```text
schema_version
route
week_of
query_text
verdict
selected_note_id
supporting_note_ids
assessments
```

Each assessment includes retrieval ranks/scores, structured-recall provenance, gate results, overlap days, evidence level, and rejection codes.

Requirements:

- Candidate objects sorted by `route`, then `week_of`.
- Assessments sorted by `note_id`.
- Canonical key order.
- ISO dates.
- JSON-native booleans, arrays, and nulls.
- Finite numeric scores only.
- Stable float serialization policy.
- Exactly one trailing newline.
- No timestamps, UUIDs, absolute machine paths, or model-generated prose.
- Atomic write and independent round-trip validation.
- SHA-256 printed by the CLI.

The audit artifact is internal and must not replace the required challenge CSV.

## 26. Supplied-data decision contract

With the Phase 5 default threshold and the Phase 6 compiled-note contract, Phase 7 must produce these decisions:

| Route | Week of | Trigger | Verdict | Selected note | Supporting notes | Why |
|---|---|---|---|---|---|---|
| Ahmedabad-Mumbai | 2025-01-20 | both | justified | N002 | none | Exact route/week festival surcharge with explicit cost impact |
| Chennai-Bangalore | 2025-02-24 | both | justified | N001 | none | Flood cost increase overlaps the full candidate week |
| Chennai-Bangalore | 2025-03-03 | both | justified | N001 | none | Flood interval overlaps Mar 3-Mar 8 |
| Chennai-Bangalore | 2025-03-10 | both | unexplained | blank | none | N001 ended Mar 8; recovery note starts Mar 17 |
| Chennai-Bangalore | 2025-03-17 | peer | unexplained | blank | none | N009 reports restored normal conditions, not an increase |
| Delhi-Jaipur | 2024-11-11 | both | unexplained | blank | none | N007 states improved roads but no transport-cost increase |
| Delhi-Jaipur | 2024-11-18 | own | unexplained | blank | none | N007 states improved roads but no transport-cost increase |
| Mumbai-Pune | 2025-06-23 | peer | partially_explained | blank | N003 | Global diesel rise may explain own movement, not peer premium |
| Mumbai-Pune | 2025-09-15 | peer | partially_explained | blank | N003 | Same global-scope limitation |
| Mumbai-Pune | 2025-10-06 | peer | partially_explained | blank | N003 | Same global-scope limitation |
| Mumbai-Pune | 2025-10-20 | peer | partially_explained | blank | N003 | Same global-scope limitation |
| Mumbai-Pune | 2025-10-27 | peer | partially_explained | blank | N003 | N010 explicitly says no rate change and cannot justify |
| Mumbai-Pune | 2025-11-03 | peer | partially_explained | blank | N003 | Global diesel context remains partial only |
| Mumbai-Pune | 2025-11-17 | peer | partially_explained | blank | N003 | Same global-scope limitation |
| Mumbai-Pune | 2025-11-24 | peer | partially_explained | blank | N003 | Same global-scope limitation |
| Mumbai-Pune | 2025-12-01 | peer | partially_explained | blank | N003 | Same global-scope limitation |
| Mumbai-Pune | 2025-12-08 | peer | partially_explained | blank | N003 | Same global-scope limitation |
| Mumbai-Pune | 2025-12-15 | peer | partially_explained | blank | N003 | Same global-scope limitation |
| Mumbai-Pune | 2025-12-22 | peer | partially_explained | blank | N003 | Same global-scope limitation |

Expected summary:

```text
Candidates reviewed: 19
Justified: 3
Partially explained: 12
Unexplained: 4
Flagged Yes: 16
Flagged No (justified): 3
Matched note ID populated: 3
Matched by N001: 2
Matched by N002: 1
Partial support from N003: 12
Output rows: 19
```

These are supplied-data regression expectations, not production hardcoding.

## 27. Important supplied-note rejection expectations

The integration suite must prove:

- N001 is accepted only for candidate weeks overlapping 2025-02-24 through 2025-03-08.
- N002 is accepted only for Ahmedabad-Mumbai during its festival week.
- N003 can support but not clear peer-driven Mumbai-Pune candidates.
- N004 is rejected because its text excludes dataset scope.
- N005 is rejected as positive evidence because costs were not significantly affected.
- N006 is rejected because operations were stable with no major disruption.
- N007 is rejected because transport-cost impact is not stated.
- N008 is rejected because movement remained normal.
- N009 is rejected because the route returned to normal.
- N010 is rejected because compliance costs were absorbed without a rate change.

No-impact notes must reject themselves only. For example, N010 must not cancel the separate partial support from N003.

## 28. Retrieval evaluation requirements

Evaluate retrieval separately from gate correctness.

Create a small labelled relevance set for the supplied candidates:

- Ahmedabad-Mumbai 2025-01-20 -> N002 relevant.
- Chennai-Bangalore 2025-02-24 -> N001 relevant.
- Chennai-Bangalore 2025-03-03 -> N001 relevant.
- Mumbai-Pune post-2025-05-05 -> N003 contextually relevant but partial.
- Clearly wrong notes are non-relevant for positive explanation.

Report:

```text
Recall@1
Recall@3
Recall@5
Mean Reciprocal Rank
```

Requirements:

- Metrics evaluate discovery only, not evidence acceptance.
- A semantically relevant but invalid note may count as retrieval-relevant for a diagnostic experiment, but the labelled set must state the convention.
- Do not use retrieval metrics as a substitute for gate tests.
- Do not tune against only the supplied 10 notes without adversarial fixtures.
- The structured-recall union must achieve 100% recall for all structurally applicable supplied notes.

Avoid asserting exact dense floating-point scores across hardware. Assert ordering, finiteness, invariants, and decisions.

## 29. Adversarial evidence matrix

Add synthetic tests covering:

| Case | Expected result |
|---|---|
| Exact route, exact week, explicit higher freight cost | Full |
| Correct event, wrong route | Rejected: route mismatch |
| Reverse-direction route | Rejected: route mismatch |
| Correct route, week before effective start | Rejected: no date overlap |
| Correct route, week after effective end | Rejected: no date overlap |
| One-day interval overlap | Date pass |
| Global diesel rise, own-only anomaly | Full if magnitude policy passes |
| Global diesel rise, peer anomaly | Partial |
| Explicit no rate change | Rejected |
| Costs not significantly affected | Rejected |
| Stable/normal operations | Rejected |
| Cost impact unknown | Rejected |
| Outside-dataset event | Rejected |
| High semantic score but wrong route | Rejected |
| Low semantic score but valid structured match | Accepted through recall union |
| Multiple full notes | Deterministic single selection |
| Multiple partial notes | Partial, selected ID null, all support IDs retained |
| Full and partial notes together | Justified; full note selected |
| No candidate notes | Unexplained |
| No-impact note plus valid independent note | Valid note still accepted |

This matrix is mandatory. It demonstrates that the project is evidence-first rather than “RAG says so.”

## 30. Public interfaces

Provide testable interfaces equivalent to:

```python
class EmbeddingProvider(Protocol):
    def encode_documents(self, texts: Sequence[str]) -> numpy.ndarray: ...
    def encode_queries(self, texts: Sequence[str]) -> numpy.ndarray: ...

def build_candidate_query(candidate: CandidateRow) -> CandidateEvidenceQuery:
    ...

def build_retrieval_document(note: CompiledContextNote) -> str:
    ...

def retrieve_sparse(
    queries: Sequence[CandidateEvidenceQuery],
    notes: Sequence[CompiledContextNote],
    top_k: int,
) -> Mapping[CandidateKey, tuple[RetrievalHit, ...]]:
    ...

def retrieve_dense(
    queries: Sequence[CandidateEvidenceQuery],
    notes: Sequence[CompiledContextNote],
    provider: EmbeddingProvider,
    top_k: int,
) -> Mapping[CandidateKey, tuple[RetrievalHit, ...]]:
    ...

def fuse_rankings(
    sparse_hits: Sequence[RetrievalHit],
    dense_hits: Sequence[RetrievalHit],
    config: RetrievalConfig,
) -> tuple[RetrievalHit, ...]:
    ...

def structured_recall(
    candidate: CandidateRow,
    notes: Sequence[CompiledContextNote],
) -> tuple[str, ...]:
    ...

def assess_evidence(
    candidate: CandidateRow,
    note: CompiledContextNote,
    retrieval: RetrievalHit,
    policy: EvidencePolicy,
) -> EvidenceAssessment:
    ...

def decide_evidence(
    candidate: CandidateRow,
    assessments: Sequence[EvidenceAssessment],
) -> EvidenceDecision:
    ...
```

Requirements:

- Query, document, fusion, recall, gate, and decision functions are pure or nearly pure.
- Model loading exists behind the provider adapter.
- File I/O exists only in orchestration/reporting boundaries.
- Inputs are not mutated.
- No function reads raw challenge files directly.

## 31. Required end-to-end procedure

Implement the pipeline in this order:

1. Load and validate Phase 2 inputs once.
2. Calculate Phase 3 weekly metrics.
3. Add Phase 4 baselines.
4. Calculate Phase 5 comparisons and candidates.
5. Compile Phase 6 context notes.
6. Validate candidate and compiled-note contracts.
7. Build candidate queries.
8. Build note retrieval documents.
9. Run sparse retrieval.
10. Load the local embedding provider lazily.
11. Run dense retrieval.
12. Fuse rankings.
13. Add structured route/time recall notes.
14. Assess every candidate-note pair in the union.
15. Aggregate assessments into one decision per candidate.
16. Build validated evidence packets.
17. Write and round-trip validate the audit JSONL.
18. Build and write the evidence-reviewed eight-column CSV.
19. Validate CSV structure, mappings, and candidate preservation.
20. Print deterministic summary counts and hashes.

If any stage fails, stop and exit non-zero. Do not emit a partial reviewed CSV.

## 32. CLI contract

Create:

```bash
cd backend
python -m scripts.review_candidate_evidence
```

Suggested output:

```text
FreightGuard evidence review
Weekly route groups evaluated: 728
Candidates reviewed: 19
Compiled notes: 10
Retrieval channels: sparse + dense + structured recall
Justified: 3
Partially explained: 12
Unexplained: 4
Flagged Yes: 16
Flagged No (justified): 3
Matched note IDs: 3
Audit contract: PASS
CSV contract: PASS
Audit: backend/data/output/evidence_gate_audit.jsonl
Audit SHA-256: <hash>
CSV: backend/data/output/evidence_reviewed_anomalies.csv
CSV SHA-256: <hash>
```

Counts and hashes must be calculated, not hardcoded.

### Model preparation command

Provide a separate explicit command such as:

```bash
cd backend
python -m scripts.prepare_embedding_model
```

It must:

- Download or resolve only the configured pinned model.
- Print the final local model location and revision.
- Avoid printing signed URLs or credentials.
- Be safe to rerun.
- Not run automatically during tests.

After preparation, the evidence-review CLI should be able to run with network disabled when `EMBEDDING_LOCAL_ONLY=true`.

## 33. Unit-test requirements

### Query tests

- Exact stable query text.
- ISO candidate-week interval.
- Trigger labels for own, peer, and both.
- Missing peer comparison formatting.
- Full-precision values retained.
- Input candidate unchanged.

### Sparse retrieval tests

- Exact route/event terms rank relevant notes strongly.
- Bigram configuration behaves as intended.
- Scores are finite.
- Deterministic tie-break by note ID.
- Empty vocabulary fails clearly.
- Repeated results are equal.

### Dense retrieval tests

- Fake provider vectors produce expected ranking.
- Document/query provider methods are used correctly.
- Vector dimension mismatch fails.
- NaN/infinite vectors fail.
- Normalization is enforced.
- Model/provider is not loaded during unrelated imports.

### Fusion tests

- Exact RRF formula.
- One-based ranks.
- Missing-channel contribution equals zero.
- Configurable weights.
- Invalid configuration rejected.
- Stable tie-break.
- Top-k clamp.

### Structured recall tests

- Exact route + overlap included.
- Global + overlap included.
- Wrong route excluded.
- No-overlap excluded.
- Open-ended interval handled.
- No-impact note still recalled structurally.
- Input order does not affect output.

### Gate tests

Implement every row in Section 29.

### Decision tests

- Full evidence -> justified.
- Partial only -> partially explained.
- Rejected only -> unexplained.
- Full outranks partial.
- Exact route outranks global.
- Overlap-day ordering.
- Final note-ID tie-break.
- Partial decision never populates selected note.
- Rejected notes never enter supporting IDs.

### Output tests

- Exact eight-column header and order.
- All candidates retained.
- Exact verdict-to-flag mapping.
- Matched note only for justified rows.
- Deterministic template reason.
- RFC-safe quoting.
- No index column.
- Stable sort and byte output.

### Audit tests

- Canonical JSON key order.
- All assessed notes represented.
- Rejection codes stable and sorted.
- Retrieval provenance preserved.
- Round-trip typed equality.
- Identical runs produce identical bytes and hash.

## 34. Integration and regression tests

The supplied-data integration test must run Phases 2 through 7 and assert:

- 728 weekly route groups.
- 19 candidate anomalies.
- 10 compiled notes.
- 19 evidence decisions.
- 3 justified decisions.
- 12 partially explained decisions.
- 4 unexplained decisions.
- Exact candidate/verdict/note mapping from Section 26.
- 19 reviewed CSV rows.
- 3 populated `matched_note_id` values.
- 16 `flagged = Yes` values.
- 3 `flagged = No (justified)` values.
- Candidate keys and numerical display fields match Phase 5 exactly.
- Audit and CSV artifacts pass independent validation.
- Candidate and source-note inputs remain unchanged.

Do not assert exact real-model floating-point scores. Pin the model and assert stable outcome-level behaviour.

## 35. Analytical invariants

### Candidate preservation

```text
reviewed candidate keys == Phase 5 candidate keys
```

### Decision cardinality

```text
one and only one decision per candidate
```

### Verdict partition

```text
justified + partially_explained + unexplained == candidate count
```

### Match integrity

- Justified implies non-null selected note.
- Non-justified implies null selected note.
- Selected note must have a full assessment.
- Supporting note IDs must have partial assessments.
- Rejected note IDs cannot be selected or supporting.

### Gate authority

- No retrieval score directly changes a verdict.
- Every selected/supporting note passed all hard gates.
- Every rejected note has at least one rejection code.

### Output reconciliation

- `No (justified)` count equals justified count.
- Populated `matched_note_id` count equals justified count.
- Output rows equal candidate count.
- Output candidate keys are unique.

## 36. Error handling

Reuse or extend focused domain exceptions, for example:

```text
EvidenceError
├── EvidenceInputError
├── RetrievalConfigurationError
├── EmbeddingProviderError
├── RetrievalContractError
├── EvidenceGateError
└── EvidenceDecisionError

ReportingError
├── EvidenceAuditError
└── EvidenceOutputContractError
```

Raise clear errors for:

- Missing candidate columns.
- Duplicate candidate keys.
- Invalid candidate week.
- Duplicate note IDs.
- Invalid retrieval configuration.
- Missing local model files.
- Vector shape or finite-value failure.
- Inconsistent compiled claims.
- Missing decision for a candidate.
- Selected note that did not pass the gate.
- Output row mismatch.
- Audit or CSV round-trip failure.

Never silently classify a pipeline error as `unexplained`; `unexplained` is a valid evidence result, not an exception fallback.

## 37. Determinism and reproducibility

- Pin model identity and revision.
- Sort corpus documents by note ID before encoding.
- Sort candidate queries by route/week before encoding.
- Normalize embeddings.
- Use deterministic CPU inference where practical.
- Avoid model dropout during inference.
- Use stable tie-breaks everywhere.
- Never place model scores in the challenge CSV.
- Keep gate decisions independent from fragile floating-point thresholds.
- Structured recall must protect outcome correctness from retrieval rank drift.
- Repeated identical runs must produce identical verdicts, selected note IDs, reviewed CSV bytes, and audit structure.

Small cross-platform float differences in audit scores may occur. If exact audit bytes are a requirement, serialize scores to a documented fixed precision for diagnostics only. Never round before ranking or gate logic.

The formal three-run reproducibility report remains Phase 9 work, but Phase 7 must be deterministic by construction.

## 38. Performance requirements

- Load source data once per CLI run.
- Encode the 10-note corpus once.
- Batch the 19 candidate queries.
- Use in-memory NumPy operations.
- No database or vector database.
- No multiprocessing.
- No external API.
- Avoid model initialization in test collection or application import.
- End-to-end CPU execution should fit ordinary local demo timeouts after the model is present locally.

## 39. Logging requirements

Log:

- Embedding model name/path and pinned revision.
- Retrieval configuration.
- Candidate count and note count.
- Retrieval latency per channel.
- Structured-recall additions.
- Verdict counts.
- Rejection-code counts.
- Output paths, validation status, and hashes.

Do not log:

- Full embeddings.
- Entire DataFrames.
- Entire note bodies by default.
- Secrets or signed download URLs.
- LLM costs or tokens because no LLM exists in this phase.

## 40. Documentation updates

### README

Add:

- Phase 7 status.
- Hybrid retrieval architecture.
- Clear statement that similarity does not decide evidence validity.
- Structured-recall safety-net explanation.
- Evidence Gate checks and verdict meanings.
- Global-versus-peer anomaly policy.
- Model preparation command.
- Offline evidence-review command.
- Audit and reviewed CSV locations.
- Expected supplied-data summary.
- Warning that Phase 8 still owns final generated wording.

### `.env.example`

Add the settings in Section 10 with safe defaults and comments.

### `docs/DECISIONS.md`

Add decisions equivalent to:

```text
ADR-034: Use hybrid sparse and dense retrieval for note discovery
ADR-035: Fuse retrieval channels with deterministic Reciprocal Rank Fusion
ADR-036: Union retrieval with structured route/time recall
ADR-037: Give the Evidence Gate sole authority over verdicts and note matching
ADR-038: Keep global evidence partial for peer-driven anomalies
ADR-039: Populate matched_note_id only for full justification
ADR-040: Preserve rejected-note reasons in a deterministic audit trail
ADR-041: Use local pinned embeddings without a vector database
```

### Implementation checklist

Mark Phase 7 complete only after all acceptance criteria pass. Do not mark Phase 8 started.

## 41. Security and robustness requirements

- Treat source note text as untrusted data.
- Never execute instructions embedded in notes.
- Never include source note text in shell commands.
- Keep model preparation explicit and revision-pinned.
- Do not enable remote custom model code unless reviewed and explicitly required.
- Prefer safe tensor/model formats supported by the pinned stack.
- Validate model path boundaries where repository policy requires it.
- No candidate or note should control configuration.
- Do not expose absolute machine paths in output artifacts.
- A malicious note may affect similarity ranking but can never bypass structured gates.

## 42. Explicit non-goals for Phase 7

Codex must not implement:

- LLM explanation generation.
- Prompt templates for a generative model.
- OpenAI, Gemini, Anthropic, or other hosted model calls.
- Token or API-cost accounting.
- Fine-tuning.
- A vector database.
- Approximate nearest-neighbour infrastructure.
- Human feedback workflows.
- Final Phase 8 explanation validation.
- Phase 9 three-run evaluation reports.
- New FastAPI endpoints.
- React pages or charts.
- Database persistence.
- Docker or cloud deployment.
- Natural-language Q&A.

## 43. Required verification commands

Adapt commands to the repository and report exact results.

### Complete backend suite

```bash
python -m pytest backend/tests -q
```

### Focused Phase 7 suite with coverage

```bash
python -m pytest \
  backend/tests/unit/evidence \
  backend/tests/unit/retrieval \
  backend/tests/integration/test_evidence_pipeline_supplied_data.py \
  backend/tests/integration/test_evidence_outputs.py \
  -q --cov=backend/app/services/evidence \
  --cov=backend/app/services/retrieval \
  --cov=backend/app/services/reporting
```

### Lint

```bash
python -m ruff check backend
```

### Model preparation and offline review

```bash
cd backend
python -m scripts.prepare_embedding_model
python -m scripts.review_candidate_evidence
```

After the preparation step succeeds, repeat the review with network disabled or an enforced local-only setting.

### Prior phase inspections

```bash
cd backend
python -m scripts.validate_inputs
python -m scripts.inspect_weekly_metrics
python -m scripts.inspect_baselines
python -m scripts.generate_candidate_output
python -m scripts.compile_context_notes
python -m scripts.review_candidate_evidence
```

No command may remain waiting indefinitely. Use sensible timeouts and non-interactive operation.

## 44. Acceptance criteria

Phase 7 is complete only when every applicable condition passes:

- [ ] All Phase 1 through Phase 6 tests still pass.
- [ ] Phase 5 candidate calculations remain unchanged.
- [ ] Phase 6 compiled notes are consumed directly.
- [ ] Query text is deterministic and candidate-derived.
- [ ] Sparse retrieval works and is deterministic.
- [ ] Dense retrieval uses a local pinned embedding model.
- [ ] Tests never download model weights.
- [ ] Sparse and dense ranks are fused with the documented RRF formula.
- [ ] Structured route/time recall is unioned with hybrid top-k.
- [ ] Similarity scores never directly determine verdicts.
- [ ] Wrong-route notes are rejected.
- [ ] Reverse-direction routes are rejected.
- [ ] Wrong-date notes are rejected.
- [ ] Outside-dataset notes are rejected.
- [ ] No-impact and no-rate-change notes are rejected.
- [ ] Normal/stable-operation notes are rejected as positive evidence.
- [ ] Unknown cost impact is not treated as false or positive evidence.
- [ ] Event-specific negation does not cancel unrelated valid evidence.
- [ ] Exact route evidence can fully justify applicable candidates.
- [ ] Global evidence cannot fully clear peer-driven anomalies.
- [ ] Multiple partial notes cannot combine into full justification.
- [ ] Every candidate receives exactly one verdict.
- [ ] Selected note exists only for justified candidates.
- [ ] Partial support IDs remain internal and traceable.
- [ ] Rejected note IDs cannot enter the Phase 8 allowlist.
- [ ] All 19 candidate rows remain in reviewed output.
- [ ] Reviewed CSV has exactly eight required columns.
- [ ] `No (justified)` and `matched_note_id` mappings are exact.
- [ ] Audit JSONL records retrieval provenance and gate failures.
- [ ] Both artifacts pass independent round-trip validation.
- [ ] Repeated identical runs preserve decisions and output bytes.
- [ ] Supplied data produces exactly 3 justified, 12 partial, and 4 unexplained decisions.
- [ ] Supplied-data candidate/note mapping exactly matches Section 26.
- [ ] README, environment example, and decision records are updated.
- [ ] Ruff reports no errors.
- [ ] No Phase 8 or later functionality is implemented.
- [ ] Codex reports files, decisions, commands, metrics, counts, hashes, limitations, and commit message.
- [ ] Codex stops after Phase 7.

## 45. Suggested implementation sequence

1. Add evidence enums and immutable contracts.
2. Add candidate-query and retrieval-document builders.
3. Add sparse retrieval and tests.
4. Add embedding-provider protocol and fake test provider.
5. Add local dense retriever and tests.
6. Add RRF fusion and tests.
7. Add structured recall and tests.
8. Add hard Evidence Gate checks and adversarial matrix.
9. Add verdict aggregation and deterministic selection.
10. Add validated Phase 8 evidence packets.
11. Add audit JSONL writer and validator.
12. Add evidence-reviewed CSV mapping through the Phase 5 writer.
13. Add supplied-data regression fixture and integration tests.
14. Add model-preparation and evidence-review CLIs.
15. Run offline verification, all tests, lint, and output inspection.
16. Update documentation and checklist.
17. Stop before Phase 8.

## 46. Official implementation references

Use current official documentation while adapting APIs to the pinned dependency versions:

- Sentence Transformers semantic search: <https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html>
- SentenceTransformer encode API: <https://www.sbert.net/docs/package_reference/sentence_transformer/model.html>
- `all-MiniLM-L6-v2` model card: <https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2>
- scikit-learn `TfidfVectorizer`: <https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html>

Do not copy example code blindly. Use the repository’s pinned versions, provider abstractions, error handling, and deterministic contracts.

## 47. Suggested Phase 7 commit message

```text
feat: add hybrid retrieval and deterministic evidence gate
```

## 48. Required completion report from Codex

When Phase 7 is finished, Codex must report:

1. What was implemented.
2. Every file created or modified.
3. Important decisions and deviations from this plan.
4. Commands executed and exact results.
5. Sparse, dense, fused, and structured-recall metrics.
6. Verdict counts and exact candidate/note mapping.
7. Rejection-code counts.
8. Model name, revision, and offline-run result.
9. Audit and CSV contract-validation results and SHA-256 hashes.
10. Confirmation that Phase 5 candidate calculations remained unchanged.
11. Exact manual verification steps.
12. Limitations or blockers.
13. A concise Git commit message.

## 49. Copy-paste instruction for Codex

```text
Read AGENTS.md, docs/PROJECT_SPEC.md, docs/IMPLEMENTATION_PLAN.md,
docs/DECISIONS.md, FREIGHTGUARD_MASTER_IMPLEMENTATION_ROADMAP.md,
FREIGHTGUARD_PHASE_5_CANDIDATE_DETECTION_OUTPUT_PLAN.md,
FREIGHTGUARD_PHASE_6_CONTEXT_NOTE_COMPILER_PLAN.md, and
FREIGHTGUARD_PHASE_7_HYBRID_RETRIEVAL_EVIDENCE_GATE_PLAN.md completely before
editing.

Inspect the repository and verify that Phases 1 through 6 are complete.
Preserve unrelated work and follow the established package and test
conventions. Do not rewrite correct ingestion, analytics, baseline, candidate,
CSV, or context-compilation logic.

Implement Phase 7 only according to
FREIGHTGUARD_PHASE_7_HYBRID_RETRIEVAL_EVIDENCE_GATE_PLAN.md.

Consume the canonical Phase 5 candidate metrics and Phase 6 typed compiled
notes. Build deterministic candidate queries and retrieval documents. Implement
TF-IDF sparse retrieval, local Sentence Transformers dense retrieval behind an
EmbeddingProvider protocol, weighted Reciprocal Rank Fusion, and a structured
route/time recall safety net. Pin the model revision, load it lazily, and keep
tests independent of downloads through a deterministic fake provider.

Implement the deterministic Evidence Gate as the only verdict authority. Check
compiled-claim consistency, dataset scope, exact directional route, inclusive
date overlap, explicit positive transport-cost impact, direction, negation, and
explanatory scope. Similarity scores may retrieve notes but can never override
a failed gate.

Use these verdict rules: full evidence produces justified; partial evidence
without full evidence produces partially_explained; otherwise produce
unexplained. Exact route-specific valid evidence may fully justify. Global
evidence must remain partial whenever the candidate breaches the peer
threshold, because an all-routes factor does not explain a route-specific peer
premium. Do not combine multiple partial notes into full evidence.

Select at most one full matched note deterministically. Keep selected_note_id
null for partial and unexplained decisions. Retain accepted partial note IDs
internally. Ensure rejected notes never enter the Phase 8 allowed-note list.

Write deterministic evidence_gate_audit.jsonl and
evidence_reviewed_anomalies.csv. Keep all Phase 5 candidate rows. Map justified
to flagged = No (justified) with a populated matched_note_id. Map partial and
unexplained to flagged = Yes with a blank matched_note_id. Use only the
deterministic Phase 7 reason templates; do not call an LLM.

The supplied data must produce exactly 19 decisions: 3 justified, 12 partially
explained, and 4 unexplained. The exact candidate/note mapping must match
Section 26 of the plan. Never hardcode these supplied IDs or outcomes in
production logic.

Add focused query, sparse retrieval, fake-provider dense retrieval, fusion,
structured recall, gate, decision, output, audit, adversarial, offline, and
supplied-data integration tests. Run all backend tests, focused Phase 7
coverage, Ruff, prior phase inspection commands, model preparation, evidence
review, and an enforced local-only rerun with sensible timeouts.

Do not implement Phase 8 LLM explanations, prompts, API calls, token accounting,
vector databases, FastAPI endpoints, React, databases, Docker, or deployment.

When finished, report the 13 items listed in Section 48. Update the Phase 7
checklist, then stop. Do not begin Phase 8.
```
