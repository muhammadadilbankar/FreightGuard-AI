# FreightGuard AI - Phase 6 Context-Note Compiler Implementation Plan

## 1. Purpose of this document

This document is the complete implementation contract for Phase 6 of FreightGuard AI. Give it to Codex only after Phases 1 through 5 have been completed, tested, and committed.

Phase 6 converts the validated free-text context notes from Phase 2 into typed, deterministic, traceable evidence claims. It preserves every source note exactly while extracting route scope, effective dates, event type, transport-cost impact, direction, negation, and magnitude.

Phase 6 is a compiler, not an evidence judge. It must not retrieve notes for a candidate, select a matched note, clear an anomaly, modify the Phase 5 CSV, or generate a final explanation. Those decisions belong to Phase 7 and later.

## 2. Phase objective

Build a context-note compilation layer that:

- Consumes the canonical Phase 2 context-note DataFrame.
- Accepts the known directional route universe explicitly.
- Preserves `note_id`, source date, `applies_to`, and note text.
- Converts route applicability into a typed scope representation.
- Resolves explicit, weekly, quarterly, approximate, and open-ended time intervals.
- Classifies event type using deterministic rules.
- Separates event meaning from transport-cost impact.
- Represents explicit increases, explicit no-impact statements, stable operations, and unknown impact differently.
- Detects negated cost or rate impact.
- Extracts quantitative magnitude text without inventing a number.
- Uses safe `unknown` values and compilation warnings when a claim is ambiguous.
- Produces a deterministic, schema-versioned JSONL inspection artifact.
- Provides a CLI for compiling and inspecting all notes.
- Adds unit, integration, determinism, and supplied-data regression tests.

After Phase 6, Phase 7 must be able to retrieve candidate notes and apply strict route, date, direction, cost-impact, and scope gates without reparsing raw note text.

## 3. Preconditions

Before editing, Codex must verify:

- Phases 1 through 5 are complete.
- All existing backend tests pass.
- The Phase 2 loader returns exactly the canonical note columns in order:

```text
note_id
date
applies_to
note
```

- The supplied context file contains 10 validated notes.
- The normalized shipment data exposes the seven known directional routes.
- Phase 5 produces 19 candidate anomalies with the default 20% threshold.
- The Phase 5 candidate decisions and CSV are unchanged by this phase.
- Generated output directories remain excluded from Git unless the repository explicitly tracks fixtures.
- The original challenge files remain unchanged.
- The Git working tree is inspected and unrelated changes are preserved.

For the provided dataset, the source context file currently has this SHA-256:

```text
875c57a896ac3dfac0f712f8865b287bb5d2bd5423d26e798297b74dce87e6dc
```

Treat this hash as a regression observation, not as production logic. Never hardcode it into the compiler.

If the implemented repository uses equivalent names or locations, adapt to its existing conventions rather than rewriting correct earlier-phase code. Report any material deviation.

## 4. Phase boundary

### Phase 6 owns

- Typed compiled-note contracts.
- Route-scope normalization.
- Effective-interval compilation.
- Event-type classification.
- Cost-impact and direction classification.
- Negation recognition.
- Magnitude-text extraction.
- Compilation warnings and trace metadata.
- Deterministic serialization for inspection.
- Tests for compilation correctness.

### Phase 6 does not own

- Candidate-to-note retrieval.
- Embeddings or vector indexes.
- Candidate/note similarity scores.
- Final route/date/evidence acceptance.
- A `justified`, `unexplained`, or `partially_explained` verdict.
- `flagged = No (justified)` decisions.
- Selection of `matched_note_id`.
- Modification of `candidate_anomalies.csv`.
- Natural-language explanation generation.
- LLM provider integration.
- API endpoints, frontend views, or persistence.

The compiler may identify structural properties such as global scope, explicit route scope, outside-dataset wording, and explicit cost negation. Phase 7 alone decides whether those properties satisfy the evidence contract for a specific candidate.

## 5. Input contract

The compiler consumes the validated Phase 2 context-note DataFrame with exactly these canonical fields:

```text
note_id
date
applies_to
note
```

Input preconditions:

- The DataFrame is not empty.
- Required columns exist exactly once.
- `note_id` values are unique, non-blank strings.
- `date` values are timezone-naive dates or normalized timestamps.
- `applies_to` values are non-blank strings.
- `note` values are non-blank strings.
- The original note text has not been summarized or rewritten.
- The known-route collection is non-empty, unique, and contains normalized directional route strings.
- Route direction is preserved. `Mumbai-Pune` and `Pune-Mumbai` are different.

The compiler must not read CSV files directly. A thin CLI orchestration layer may call the Phase 2 loader once and pass its result into the compiler.

## 6. Core design decision: typed uncertainty

A binary `affects_transport_cost` value alone cannot safely represent all supplied notes. For example:

- “pushing up transportation costs” is explicit positive cost evidence.
- “costs were not significantly affected” is an explicit no-material-impact statement.
- “without a rate change” explicitly negates a rate increase.
- “improved road conditions” describes an event but does not state a cost effect.

Therefore, use a typed `cost_impact_status` as the authoritative field and derive a nullable compatibility field:

```text
affects_transport_cost = true
    only for explicit increase or explicit decrease

affects_transport_cost = false
    for explicit no-impact, no-rate-change, or normal/stable-operation claims

affects_transport_cost = null
    when transport-cost impact is not stated or cannot be resolved safely
```

Never coerce `unknown` into `false`. Phase 7 must reject both `false` and `null` when positive transport-cost impact is required, but the distinction remains valuable for audit and future review.

## 7. Canonical compiled-note schema

Define a typed immutable model equivalent to:

```python
class CompiledContextNote(BaseModel):
    schema_version: Literal["1.0"]
    note_id: str
    source_date: date
    source_applies_to: str
    original_text: str

    scope_type: ScopeType
    applies_to_routes: tuple[str, ...]
    scope_status: ScopeStatus

    effective_from: date
    effective_to: date | None
    temporal_basis: TemporalBasis

    event_type: EventType
    impact_direction: ImpactDirection
    cost_impact_status: CostImpactStatus
    affects_transport_cost: bool | None
    negates_cost_increase: bool
    magnitude_text: str | None

    compilation_warnings: tuple[str, ...]
```

Use Pydantic v2 if it is already an established dependency. Otherwise use an immutable dataclass plus explicit validation. Do not add a second validation framework.

### Field semantics

| Field | Meaning |
|---|---|
| `schema_version` | Version of the compiled-note contract, initially `1.0` |
| `note_id` | Original unique source identifier |
| `source_date` | Original normalized note date |
| `source_applies_to` | Original normalized `applies_to` value |
| `original_text` | Exact note text from Phase 2 |
| `scope_type` | `global`, `route`, or `unknown` |
| `applies_to_routes` | Sorted unique explicit routes; empty for global or unresolved scope |
| `scope_status` | Whether scope is usable, outside dataset, or unresolved |
| `effective_from` | Inclusive start date |
| `effective_to` | Inclusive end date, or null when explicitly/open-ended |
| `temporal_basis` | How the interval was obtained |
| `event_type` | Deterministic event taxonomy |
| `impact_direction` | Direction of transport-cost impact, not general sentiment |
| `cost_impact_status` | Authoritative typed claim about cost/rates |
| `affects_transport_cost` | Derived nullable convenience field |
| `negates_cost_increase` | True when the text explicitly rules out an active increase |
| `magnitude_text` | Exact quantitative magnitude phrase, if present |
| `compilation_warnings` | Stable warning codes, never prose generated by an LLM |

## 8. Enumerations

Keep enum values lowercase and stable because they become serialized contract values.

### 8.1 Scope type

```text
global
route
unknown
```

### 8.2 Scope status

```text
in_dataset
outside_dataset
partially_in_dataset
unresolved
```

Rules:

- `global` normally maps to `in_dataset` because it applies to all known routes.
- Explicit wording that the affected routes are not part of the dataset maps to `outside_dataset` even when `applies_to` says `All Routes`.
- A single explicit known route maps to `in_dataset`.
- An explicit unknown route maps to `outside_dataset` and receives a warning.
- Multiple route support is allowed for future inputs even though the supplied file uses one route or `All Routes`.

### 8.3 Temporal basis

```text
explicit_range
calendar_week
approximate_week
calendar_quarter
open_ended_start
state_after_completion
source_date_fallback
unresolved
```

### 8.4 Impact direction

```text
increase
decrease
no_change
unknown
```

This field describes transport-cost or rate direction. A positive operational phrase such as “improved road conditions” must not automatically become `decrease` unless cost/rate direction is stated or clearly implied under an approved rule.

### 8.5 Cost-impact status

```text
explicit_increase
explicit_decrease
explicit_no_material_impact
explicit_no_rate_change
normal_or_stable_operations
not_stated
unknown
```

### 8.6 Event type

Use a compact extensible taxonomy:

```text
weather_disruption
festival_demand
fuel_price_change
toll_or_infrastructure
road_maintenance
capacity_or_demand_condition
road_improvement
normal_operations
recovery_or_normalization
regulatory_compliance
other
unknown
```

Unknown/fallback values are valid outputs. Do not fail compilation merely because a future event type is unfamiliar.

## 9. Folder and module structure

Extend the established backend structure as follows:

```text
backend/
├── app/
│   ├── domain/
│   │   └── context_notes.py
│   └── services/
│       └── context/
│           ├── __init__.py
│           ├── compiler.py
│           ├── impact.py
│           ├── scope.py
│           ├── serialization.py
│           └── temporal.py
├── scripts/
│   └── compile_context_notes.py
└── tests/
    ├── fixtures/
    │   └── context/
    │       ├── notes_compilation_cases.csv
    │       └── expected_compiled_notes.jsonl
    ├── unit/
    │   └── context/
    │       ├── test_context_compiler.py
    │       ├── test_context_impact.py
    │       ├── test_context_scope.py
    │       ├── test_context_serialization.py
    │       └── test_context_temporal.py
    └── integration/
        └── test_context_compilation_supplied_data.py
```

Responsibilities:

- `domain/context_notes.py`: enums, typed value objects, and `CompiledContextNote`.
- `context/scope.py`: route/global scope compilation and dataset-scope status.
- `context/temporal.py`: date phrase parsing and interval validation.
- `context/impact.py`: event, impact, direction, negation, and magnitude extraction.
- `context/compiler.py`: orchestration, invariants, sorting, and DataFrame/model adapters.
- `context/serialization.py`: deterministic JSONL construction, writing, reading, and contract validation.
- `scripts/compile_context_notes.py`: thin Phase 2 + Phase 6 CLI orchestration.

Equivalent module names are acceptable if they follow the implemented repository’s conventions. Do not place all parsing, orchestration, CLI, and serialization in one oversized file.

## 10. Public interfaces

Provide independently testable interfaces equivalent to:

```python
def compile_route_scope(
    applies_to: str,
    original_text: str,
    known_routes: frozenset[str],
) -> RouteScope:
    ...

def resolve_effective_interval(
    source_date: date,
    original_text: str,
) -> EffectiveInterval:
    ...

def compile_impact_claim(original_text: str) -> ImpactClaim:
    ...

def compile_context_note(
    note: ContextNoteInput,
    known_routes: frozenset[str],
) -> CompiledContextNote:
    ...

def compile_context_notes(
    context_notes: pandas.DataFrame,
    known_routes: Collection[str],
) -> tuple[CompiledContextNote, ...]:
    ...

def write_compiled_notes_jsonl(
    notes: Sequence[CompiledContextNote],
    destination: pathlib.Path,
) -> pathlib.Path:
    ...
```

Requirements:

- Core functions are pure or nearly pure.
- Dependencies are passed explicitly.
- No function mutates the input DataFrame or source strings.
- No parsing function reads files, settings, candidates, or global state.
- Rule precedence is visible and testable.
- Output order is deterministic by `note_id`.

## 11. Required compilation procedure

Implement the Phase 6 flow in this order:

1. Validate the Phase 2 note-frame contract.
2. Validate and freeze the known route universe.
3. Convert each row into a typed input object.
4. Preserve the exact original note text.
5. Compile route scope.
6. Resolve the inclusive effective interval.
7. Classify event type.
8. Classify cost-impact status.
9. Derive cost impact direction.
10. Detect explicit negation of a cost increase.
11. Extract quantitative magnitude text if present.
12. Attach stable warning codes for unresolved or suspicious claims.
13. Validate cross-field invariants.
14. Sort compiled notes by `note_id`.
15. Serialize the typed models to deterministic JSONL.
16. Read the JSONL back and validate schema and equality.
17. Print a concise compilation summary and SHA-256.

Compilation of one invalid note must fail the run with a focused error. Do not silently drop a note.

## 12. Route-scope compilation

### 12.1 Global scope

Normalize a case-insensitive, outer-whitespace-trimmed `All Routes` token to:

```text
scope_type = global
applies_to_routes = ()
```

The empty tuple means “not enumerated because scope is global,” not “applies to no route.”

### 12.2 Explicit route scope

For an explicit route:

- Preserve directional identity.
- Normalize only according to the Phase 2 route naming contract.
- Store it as a one-item tuple.
- Compare it with the injected known-route set.
- Mark it `in_dataset` when present.
- Mark it `outside_dataset` and emit `explicit_route_not_in_dataset` when absent.

Do not fuzzy-match route names in Phase 6. A typo must remain unresolved or outside the dataset, not be silently corrected.

### 12.3 Text-level scope exclusions

Detect clear exclusions such as:

```text
affected routes are not part of this dataset
outside this dataset
does not apply to routes in this dataset
```

When such wording is present:

- Set `scope_status = outside_dataset`.
- Add warning code `text_excludes_dataset_scope`.
- Preserve the original `scope_type` and `source_applies_to` for audit.
- Do not delete or rewrite the note.

This is structured claim extraction, not candidate-specific evidence acceptance.

### 12.4 Future multiple-route values

If the repository elects to support delimiter-separated routes:

- Define the accepted delimiter explicitly.
- Reject mixed/ambiguous delimiters.
- Normalize, deduplicate, and sort route values.
- Mark `partially_in_dataset` only when some routes are known and some are not.

Do not add this feature unless the input contract or fixture requires it.

## 13. Temporal compiler

All intervals are inclusive. `effective_to = null` means open-ended, not missing or invalid.

### 13.1 Rule precedence

Apply temporal rules from most specific to least specific:

1. Explicit `from <date> to <date>` range.
2. Explicit bounded duration such as “for about a week.”
3. Calendar-quarter wording such as “this quarter.”
4. Calendar-week wording such as “festival week.”
5. Open-ended start wording such as “starting this week” or “was introduced.”
6. State-after-completion wording such as “returned to normal” or “after ... completed.”
7. Conservative source-date fallback.

Never let a generic rule override a more specific interval.

### 13.2 Explicit date ranges

Support unambiguous English month names and abbreviations with day numbers, for example:

```text
from Feb 24 to Mar 8
from February 24 through March 8
```

Year resolution:

- Start from `source_date.year`.
- If the end month/day would be before the start and the text spans year-end, use the following year.
- Reject impossible calendar dates.
- Reject an end date before a start after year resolution.

### 13.3 Week rules

- “festival week” anchored at a Monday source date becomes Monday through Sunday.
- “for about a week” becomes source date through source date plus six days.
- If the source date is not Monday, a bare “this week” maps to its containing Monday-Sunday calendar week unless “starting” clearly marks an open-ended state.
- “starting this week” is open-ended unless an explicit end is also present.

### 13.4 Quarter rules

“This quarter” maps to the calendar quarter containing `source_date`:

| Source month | Effective interval |
|---|---|
| Jan-Mar | Jan 1-Mar 31 |
| Apr-Jun | Apr 1-Jun 30 |
| Jul-Sep | Jul 1-Sep 30 |
| Oct-Dec | Oct 1-Dec 31 |

Use standard calendar quarters, not fiscal quarters, because the supplied brief provides no fiscal-calendar configuration.

### 13.5 Open-ended state rules

Use an open-ended interval only when wording indicates a continuing state, for example:

- `starting this week`
- `was commissioned`
- `was introduced`
- `returned to normal`
- `after ... was completed`

Do not infer an arbitrary 30-, 60-, or 90-day duration.

### 13.6 Conservative fallback

For a valid note with no supported temporal phrase:

```text
effective_from = source_date
effective_to = source_date
temporal_basis = source_date_fallback
warning = temporal_scope_defaulted_to_source_date
```

A single-day fallback is intentionally conservative. It prevents the compiler from inventing a long validity interval.

## 14. Impact and event compiler

### 14.1 Deterministic implementation

Use explicit ordered rules built from normalized text, word-boundary-aware regular expressions, and small declarative lexicons.

Do not use:

- An LLM.
- Sentiment analysis.
- An embedding similarity score.
- A heavyweight NLP framework.
- A hardcoded mapping from `note_id` to outcome.
- A hardcoded mapping from supplied route/date pairs to outcome.

Production logic must generalize by phrase semantics. Supplied note IDs may appear only in tests and expected regression fixtures.

### 14.2 Precedence for cost impact

Explicit negation rules must run before positive keyword rules.

Required precedence:

1. Explicit no-rate-change phrases.
2. Explicit no-material-cost-impact phrases.
3. Normal/stable/no-disruption phrases.
4. Explicit cost decrease phrases.
5. Explicit cost increase phrases.
6. Cost impact not stated.
7. Unknown only when conflicting supported claims cannot be resolved.

This prevents text such as “compliance costs were absorbed ... without a rate change” from being misclassified as an increase merely because it contains the word `costs`.

### 14.3 Explicit increase examples

Recognize direct causal language such as:

```text
higher trip costs
pushing up transportation costs
surcharge applied by transporters
freight rates increased
transport costs rose
```

The rule must require transport/freight/rate/cost context. A generic increase in traffic or rainfall is not automatically a transport-cost increase.

### 14.4 Explicit no-impact and no-rate-change examples

Recognize phrases such as:

```text
costs were not significantly affected
without a rate change
no change in freight rates
absorbed by transporters
```

Classify the strongest explicit statement:

- No material cost effect -> `explicit_no_material_impact`.
- No rate change -> `explicit_no_rate_change`.
- Set `impact_direction = no_change`.
- Set `affects_transport_cost = false`.
- Set `negates_cost_increase = true`.

### 14.5 Normal/stable operations

Recognize statements that operations are stable, normal, restored, or free of significant disruption.

When no positive cost claim is also present:

```text
cost_impact_status = normal_or_stable_operations
impact_direction = no_change
affects_transport_cost = false
negates_cost_increase = true
```

Do not treat words describing an earlier event as a current positive claim when the sentence states that conditions returned to normal.

### 14.6 Impact not stated

When a note describes an event but does not state or safely imply transport-cost impact:

```text
cost_impact_status = not_stated
impact_direction = unknown
affects_transport_cost = null
negates_cost_increase = false
warning = transport_cost_impact_not_stated
```

Examples include an unrelated toll/infrastructure statement or improved road conditions with no rate/cost statement.

### 14.7 Event taxonomy rules

Event classification is independent from cost impact. For example:

- Flooding may be `weather_disruption` and explicitly increase costs.
- Highway maintenance may be `road_maintenance` while costs are explicitly unaffected.
- Normal operations may be `normal_operations` with no increase.
- A compliance mandate may be `regulatory_compliance` with no rate change.

Prefer a specific supported event rule over `other`; use `unknown` only when no safe category exists.

## 15. Magnitude extraction

Extract only an exact quantitative magnitude phrase connected to transport cost or rates.

Supported examples:

```text
5-7%
roughly 5-7%
about 6 percent
INR 2 per kilometre
```

Requirements:

- Preserve the matched text exactly as it appears, after safe outer trimming.
- Do not convert a range to a midpoint.
- Do not infer a numeric magnitude from words such as `minor`, `higher`, or `significant`.
- Do not treat durations such as `about a week` as cost magnitude.
- Return null when no cost magnitude exists.
- If multiple contradictory cost magnitudes exist, return null and add `conflicting_cost_magnitudes`.

## 16. Warning codes

Use stable machine-readable codes. At minimum support:

```text
explicit_route_not_in_dataset
text_excludes_dataset_scope
temporal_scope_defaulted_to_source_date
temporal_phrase_ambiguous
transport_cost_impact_not_stated
conflicting_cost_claims
conflicting_cost_magnitudes
event_type_unknown
```

Requirements:

- Warnings are deduplicated and lexicographically sorted.
- Warnings are not fatal unless an invariant is violated.
- Do not place dynamic prose, paths, or timestamps in warning values.
- Do not use warnings as Phase 7 verdicts.

## 17. Cross-field invariants

Validate every compiled note:

### Identity and preservation

- `note_id` is unchanged.
- `original_text` equals the Phase 2 note string byte-for-byte after normal string representation.
- `source_applies_to` is preserved.

### Scope

- Global scope has an empty `applies_to_routes` tuple.
- Route scope has at least one route.
- Routes are unique and sorted.
- `in_dataset` route scope contains only known routes.

### Time

- `effective_from` is always present.
- If `effective_to` is present, it is greater than or equal to `effective_from`.
- `unresolved` temporal basis must carry a warning.

### Impact

- `explicit_increase` implies `impact_direction = increase` and `affects_transport_cost = true`.
- `explicit_decrease` implies `impact_direction = decrease` and `affects_transport_cost = true`.
- Explicit no-impact/no-rate-change implies `impact_direction = no_change`, `affects_transport_cost = false`, and `negates_cost_increase = true`.
- `normal_or_stable_operations` implies no active increase.
- `not_stated` implies `impact_direction = unknown` and `affects_transport_cost = null`.
- A note cannot be both `explicit_increase` and `negates_cost_increase`.

If an invariant fails, raise a focused compilation error. Do not serialize inconsistent output.

## 18. Supplied-data regression contract

The implementation must derive the following results from generic rules. Production code must not key off note IDs.

| ID | Scope | Scope status | Effective from | Effective to | Temporal basis | Event type | Cost impact | Direction | Negates increase | Magnitude |
|---|---|---|---|---|---|---|---|---|---|---|
| N001 | route: Chennai-Bangalore | in_dataset | 2025-02-24 | 2025-03-08 | explicit_range | weather_disruption | explicit_increase | increase | false | null |
| N002 | route: Ahmedabad-Mumbai | in_dataset | 2025-01-20 | 2025-01-26 | calendar_week | festival_demand | explicit_increase | increase | false | null |
| N003 | global | in_dataset | 2025-05-05 | null | open_ended_start | fuel_price_change | explicit_increase | increase | false | roughly 5-7% |
| N004 | global | outside_dataset | 2024-03-11 | null | open_ended_start | toll_or_infrastructure | not_stated | unknown | false | null |
| N005 | route: Mumbai-Delhi | in_dataset | 2024-07-29 | 2024-08-04 | approximate_week | road_maintenance | explicit_no_material_impact | no_change | true | null |
| N006 | global | in_dataset | 2025-07-01 | 2025-09-30 | calendar_quarter | capacity_or_demand_condition | normal_or_stable_operations | no_change | true | null |
| N007 | route: Delhi-Jaipur | in_dataset | 2024-05-20 | null | state_after_completion | road_improvement | not_stated | unknown | false | null |
| N008 | route: Kolkata-Bhubaneswar | in_dataset | 2025-04-01 | 2025-06-30 | calendar_quarter | normal_operations | normal_or_stable_operations | no_change | true | null |
| N009 | route: Chennai-Bangalore | in_dataset | 2025-03-17 | null | state_after_completion | recovery_or_normalization | normal_or_stable_operations | no_change | true | null |
| N010 | global | in_dataset | 2025-10-27 | null | open_ended_start | regulatory_compliance | explicit_no_rate_change | no_change | true | null |

Expected supplied-data summary:

```text
Notes compiled: 10
Global-scope notes: 4
Route-scope notes: 6
Explicit cost-increase notes: 3
Explicit no-material-impact notes: 1
Explicit no-rate-change notes: 1
Normal/stable-operation notes: 3
Cost impact not stated: 2
Dataset-scope exclusions: 1
Open-ended intervals: 5
Bounded intervals: 5
Compilation failures: 0
```

The bounded/open-ended counts treat any non-null `effective_to` as bounded.

Regression tests must compare every contract field, not only row count.

## 19. Deterministic JSONL inspection artifact

Write:

```text
backend/data/output/compiled_context_notes.jsonl
```

JSONL is preferred over CSV because it safely represents arrays, null values, booleans, and warnings without delimiter conventions.

Serialization requirements:

- UTF-8.
- One JSON object per line.
- Notes sorted by `note_id`.
- Object keys written in the canonical schema order.
- Dates serialized as `YYYY-MM-DD`.
- Tuples serialized as JSON arrays.
- Null retained as JSON `null`.
- Booleans retained as JSON booleans.
- `ensure_ascii = false`.
- Stable compact separators.
- Exactly one trailing newline.
- No timestamps, UUIDs, machine paths, model metadata, or random values.
- Atomic replacement through a temporary file where practical.

After writing:

1. Read every line through an independent path.
2. Parse JSON strictly.
3. Validate every object against the typed model.
4. Confirm count, order, and equality with the in-memory models.
5. Calculate SHA-256.

The JSONL artifact is diagnostic input for Phase 7, not the challenge’s final submission file.

## 20. CLI contract

Create:

```bash
cd backend
python -m scripts.compile_context_notes
```

The command must:

1. Load settings once.
2. Load and validate Phase 2 input data once.
3. Derive the known directional route universe from normalized shipments.
4. Compile all validated context notes.
5. Validate compiled-note invariants.
6. Write `compiled_context_notes.jsonl` to the configured output directory.
7. Read and validate the artifact.
8. Print a concise deterministic summary.

Suggested output:

```text
FreightGuard context-note compilation
Notes compiled: 10
Global scope: 4
Route scope: 6
Explicit cost increases: 3
Explicit no-impact/no-rate-change: 2
Normal or stable operations: 3
Cost impact not stated: 2
Dataset-scope exclusions: 1
Output contract: PASS
Output: backend/data/output/compiled_context_notes.jsonl
SHA-256: <calculated hash>
```

Counts and hash must be calculated, not hardcoded. The command must exit non-zero on input, compilation, invariant, write, or round-trip validation failure.

## 21. Unit-test requirements

### 21.1 Scope tests

Test:

- `All Routes` with case/outer-whitespace variation.
- Known explicit directional route.
- Reversed route remains distinct.
- Unknown explicit route.
- Global scope with explicit outside-dataset text.
- Blank and malformed scope rejection at the correct layer.
- Input route set is not mutated.
- Deterministic route ordering if multiple routes are supported.

### 21.2 Temporal tests

Test:

- Same-month explicit range.
- Cross-month explicit range.
- Cross-year explicit range.
- Invalid date.
- End before start.
- Festival/calendar week.
- Approximate one-week duration.
- `this quarter` in each of four calendar quarters.
- `starting this week` open-ended semantics.
- Introduced/commissioned open-ended semantics.
- Returned-to-normal state semantics.
- Conservative source-date fallback.
- Specific-rule precedence over generic phrases.
- Leap-year boundaries.
- Inclusive end dates.

### 21.3 Impact tests

Test:

- Explicit higher transport costs.
- Transporter surcharge.
- Fuel price increase tied to transport cost.
- Generic event increase without cost context does not become a cost increase.
- `costs were not significantly affected` wins over disruption keywords.
- `without a rate change` wins over compliance-cost keywords.
- Stable demand and no disruption.
- Returned to normal does not preserve the prior flood increase.
- Improved road conditions without cost language remains `not_stated`.
- Conflicting positive and negative claims produce `unknown` plus warning.
- Case and punctuation variation.
- Word boundaries prevent substring false positives.

### 21.4 Magnitude tests

Test:

- `roughly 5-7%` is preserved.
- `about 6 percent` is preserved.
- A currency-per-distance magnitude is preserved.
- `about a week` is not extracted as cost magnitude.
- `minor delays` produces null magnitude.
- Multiple conflicting cost magnitudes generate a warning.

### 21.5 Model and invariant tests

Test:

- Every enum rejects arbitrary values.
- End date cannot precede start date.
- Global scope cannot contain explicit routes.
- `explicit_increase` cannot derive `affects_transport_cost = false`.
- `not_stated` cannot derive a non-unknown direction.
- Warnings are unique and sorted.
- Models are immutable if the chosen framework supports it.

### 21.6 Preservation and immutability tests

Test:

- Original punctuation, commas, percentages, and capitalization survive.
- Input DataFrame remains unchanged.
- Input route collection remains unchanged.
- Repeated calls produce equal typed models.
- Shuffled note input produces the same sorted output.

### 21.7 Serialization tests

Test:

- Exact key order.
- Correct JSON null/boolean/array types.
- Non-ASCII round trip.
- Embedded quotes and newlines round trip.
- One object per logical line after JSON encoding.
- Exactly one trailing newline.
- Headerless empty output is not allowed because Phase 2 rejects an empty context dataset.
- Two writes produce identical bytes and SHA-256.
- Failed write does not leave a partial destination.

## 22. Supplied-data integration tests

Compose the Phase 2 loader with the Phase 6 compiler.

Assert:

- Exactly 10 input notes compile.
- No note is added, dropped, duplicated, or reordered nondeterministically.
- All 10 expected note IDs are present exactly once.
- All original text is identical to the Phase 2 DataFrame.
- The six route-scoped and four global-scoped counts match.
- The exact regression table in Section 18 matches.
- The known-route set contains seven routes.
- The outside-dataset text in N004 is retained as a scope exclusion.
- N005 and N010 are not positive cost claims.
- N006, N008, and N009 are normal/stable rather than positive evidence.
- N007 does not infer a cost decrease from improved roads.
- Only N003 contains extracted quantitative magnitude.
- JSONL round-trip equality passes.
- Phase 5 candidate results and preliminary CSV bytes remain unchanged when Phase 6 is run.

The last assertion protects phase isolation: compiling notes must not mutate or reinterpret candidate decisions.

## 23. Error handling

Reuse or extend the existing domain hierarchy cleanly, for example:

```text
ContextCompilationError
├── ContextInputError
├── ScopeCompilationError
├── TemporalCompilationError
├── ImpactCompilationError
└── CompiledNoteContractError

ReportingError
└── CompiledNotesSerializationError
```

Raise focused errors for:

- Missing or duplicate required columns.
- Duplicate or blank note IDs.
- Invalid source date.
- Empty route universe.
- Invalid route-scope state.
- Impossible or reversed date interval.
- Contradictory cross-field impact values.
- Duplicate compiled note IDs.
- Serialization failure.
- Round-trip contract mismatch.

Expected domain errors should be concise and safe. Do not log entire note bodies on failure by default.

## 24. Performance requirements

- The corpus is small; optimize for correctness and clarity.
- Compile each note in one bounded pass through small rule sets.
- Compile regex patterns once at module load.
- Do not introduce multiprocessing, caching, a database, or a vector store.
- Do not call an external service.
- Do not add a large NLP dependency.
- The full Phase 2 + Phase 6 command should complete comfortably within ordinary local test timeouts.

## 25. Logging requirements

Log:

- Note count loaded.
- Note count compiled.
- Scope-type counts.
- Cost-impact-status counts.
- Warning count by code.
- Output path.
- Output contract status.
- SHA-256.

Do not log:

- Entire note bodies by default.
- Full DataFrames.
- Secrets.
- Candidate verdicts that do not yet exist.
- Raw exception traces for expected user/data errors in normal CLI output.

## 26. Documentation updates

### README

Add:

- Phase 6 status.
- The purpose of the context-note compiler.
- The typed uncertainty rule for transport-cost impact.
- The deterministic compilation command.
- The JSONL output location.
- A warning that compiled claims are not accepted evidence or final verdicts.
- The expected supplied-data note count.

### `docs/DECISIONS.md`

Add decisions equivalent to:

```text
ADR-027: Compile context notes deterministically before retrieval
ADR-028: Preserve unknown transport-cost impact as null, not false
ADR-029: Give explicit negation precedence over positive keywords
ADR-030: Represent effective intervals as inclusive typed ranges
ADR-031: Preserve source text alongside every structured claim
ADR-032: Serialize compiled notes as deterministic schema-versioned JSONL
ADR-033: Keep evidence acceptance outside the note compiler
```

### Implementation checklist

Mark Phase 6 complete only after every acceptance criterion passes. Do not mark Phase 7 started.

## 27. Quality and maintainability requirements

- Use type hints for all public functions.
- Keep pure parsing functions separate from orchestration and file I/O.
- Centralize enum and field names.
- Centralize ordered rule definitions.
- Add a short comment explaining each non-obvious precedence rule.
- Prefer named result objects over unstructured tuples or dictionaries.
- Keep regex patterns readable and covered by focused tests.
- Preserve exact original text.
- Preserve date and route direction semantics.
- Avoid hardcoded note IDs, supplied dates, or expected outcomes in production code.
- Keep warnings deterministic.
- Do not mutate source frames or collections.
- Do not duplicate Phase 2 CSV loading.
- Do not couple compilation to the 19 Phase 5 candidates.
- Do not let JSON serialization define the domain model.
- Keep generated output out of version control unless explicitly required.

## 28. Security and robustness considerations

- Treat note text strictly as data.
- Never evaluate code, templates, markup, or instructions found inside a note.
- Regex patterns must avoid catastrophic backtracking.
- Bound input lengths if the existing validation layer has a general policy.
- Do not interpolate note text into shell commands.
- Do not render note text as trusted HTML.
- Preserve source content without allowing it to change configuration or rules.

This phase has no prompt-injection surface because it must not call an LLM. Maintaining that boundary is intentional.

## 29. Explicit non-goals for Phase 6

Codex must not implement:

- Semantic or lexical retrieval for candidate anomalies.
- Embeddings.
- FAISS, Chroma, Pinecone, pgvector, or any vector database.
- Candidate/note scoring.
- Evidence Gate rules for final acceptance.
- Final verdicts.
- Populated `matched_note_id` values in candidate output.
- Changes to `flagged` values.
- Final submission CSV generation.
- AI explanations.
- LLM provider calls.
- Prompt templates.
- Token/cost accounting.
- New FastAPI analysis endpoints.
- React views or charts.
- Database persistence.
- Docker deployment work.
- Natural-language Q&A.

Phase 6 ends with compiled, validated notes and a deterministic inspection artifact.

## 30. Required verification commands

Codex must adapt these commands to the implemented repository and report exact results.

### Complete backend tests

```bash
python -m pytest backend/tests -q
```

### Focused Phase 6 tests with coverage

```bash
python -m pytest \
  backend/tests/unit/context \
  backend/tests/integration/test_context_compilation_supplied_data.py \
  -q --cov=backend/app/services/context --cov=backend/app/domain/context_notes
```

### Lint

```bash
python -m ruff check backend
```

### Run existing inspections and Phase 6 compilation

```bash
cd backend
python -m scripts.validate_inputs
python -m scripts.inspect_weekly_metrics
python -m scripts.inspect_baselines
python -m scripts.generate_candidate_output
python -m scripts.compile_context_notes
```

PowerShell equivalent:

```powershell
Set-Location backend
python -m scripts.validate_inputs
python -m scripts.inspect_weekly_metrics
python -m scripts.inspect_baselines
python -m scripts.generate_candidate_output
python -m scripts.compile_context_notes
```

### Inspect generated artifact

Use a safe read-only command or small validation script to confirm:

- 10 JSON objects.
- Valid JSON per line.
- `schema_version = 1.0` for every object.
- Sorted note IDs.
- Correct source-text preservation.
- Correct SHA-256 reporting.

Do not manually edit generated output. No command may wait indefinitely.

## 31. Acceptance criteria

Phase 6 is complete only when every applicable condition passes:

- [x] All Phase 1 through Phase 5 tests still pass.
- [x] The compiler consumes Phase 2 notes rather than rereading raw files.
- [x] The known route universe is injected explicitly.
- [x] The compiler returns one typed model per input note.
- [x] All 10 supplied notes compile successfully.
- [x] No note is dropped or duplicated.
- [x] Original note text is preserved exactly.
- [x] Directional routes remain directional.
- [x] Global scope and explicit route scope are distinguished.
- [x] Outside-dataset wording is represented explicitly.
- [x] Effective intervals are inclusive.
- [x] Explicit ranges, weeks, quarters, and open-ended states are supported.
- [x] Temporal rule precedence is tested.
- [x] Event classification is independent from cost-impact classification.
- [x] Explicit negation runs before positive keyword rules.
- [x] Unknown cost impact remains null rather than false.
- [x] Stable/normal notes cannot become positive evidence.
- [x] Improved conditions without cost language do not imply a cost decrease.
- [x] Quantitative magnitude is extracted without numerical invention.
- [x] Duration text is not mistaken for cost magnitude.
- [x] Warnings are stable, unique, and sorted.
- [x] Cross-field invariants are validated.
- [x] Input DataFrames and route collections are unchanged.
- [x] Shuffled input produces identical sorted output.
- [x] Repeated writes produce identical bytes and SHA-256.
- [x] JSONL validates through an independent read path.
- [x] Supplied-data results match the complete Section 18 regression table.
- [x] Phase 5 candidate decisions and CSV remain unchanged.
- [x] README and decision records are updated.
- [x] Ruff reports no errors.
- [x] No Phase 7 or later functionality is implemented.
- [x] Codex reports files, decisions, commands, counts, warnings, hash, limitations, and commit message.
- [x] Codex stops after Phase 6.

## 32. Suggested implementation sequence

Implement in small reviewable slices:

1. Add enums and immutable typed contracts.
2. Add scope compiler and tests.
3. Add temporal compiler and tests.
4. Add cost-impact/event compiler and tests.
5. Add magnitude extraction and tests.
6. Add top-level note compiler and invariants.
7. Add deterministic JSONL serialization and round-trip validation.
8. Add supplied-data integration regression fixture.
9. Add CLI.
10. Run the entire test/lint suite.
11. Update documentation and Phase 6 checklist.
12. Stop before Phase 7.

Do not postpone negation, unknown-state, or supplied-data regression tests until the end; they protect the core evidence semantics.

## 33. Suggested Phase 6 commit message

```text
feat: compile context notes into typed evidence claims
```

## 34. Required completion report from Codex

When Phase 6 is finished, Codex must report:

1. What was implemented.
2. Every file created or modified.
3. Important decisions and deviations from this plan.
4. Commands executed and exact results.
5. Compilation counts by scope, impact status, and interval type.
6. Warning counts by warning code.
7. JSONL contract-validation result and SHA-256.
8. Confirmation that the Phase 5 candidate CSV is unchanged.
9. Exact manual verification steps.
10. Limitations or blockers.
11. A concise Git commit message.

## 35. Copy-paste instruction for Codex

```text
Read AGENTS.md, docs/PROJECT_SPEC.md, docs/IMPLEMENTATION_PLAN.md,
docs/DECISIONS.md, FREIGHTGUARD_MASTER_IMPLEMENTATION_ROADMAP.md,
FREIGHTGUARD_PHASE_5_CANDIDATE_DETECTION_OUTPUT_PLAN.md, and
FREIGHTGUARD_PHASE_6_CONTEXT_NOTE_COMPILER_PLAN.md completely before editing.

Inspect the repository and verify that Phases 1 through 5 are complete.
Preserve unrelated work and follow the established package and test
conventions. Do not rewrite correct ingestion, analytics, baseline, candidate,
or CSV logic.

Implement Phase 6 only according to
FREIGHTGUARD_PHASE_6_CONTEXT_NOTE_COMPILER_PLAN.md.

Build a deterministic typed context-note compiler. Consume the canonical
Phase 2 context-note DataFrame and an explicitly injected known-route set.
Preserve the original note text exactly. Compile route scope, inclusive
effective interval, event type, cost-impact status, impact direction, explicit
negation, quantitative magnitude text, and stable warning codes.

Use typed uncertainty. The authoritative cost-impact status must distinguish
explicit increase, explicit decrease, explicit no material impact, explicit no
rate change, normal/stable operations, not stated, and unknown. Derive
affects_transport_cost as true, false, or null. Never convert an unstated
impact to false. Run explicit negation rules before positive keyword rules.

Implement generic deterministic phrase rules. Never hardcode supplied note
IDs, dates, routes, or expected outcomes in production code. Do not use an
LLM, embeddings, sentiment analysis, or a heavyweight NLP dependency.

Write schema-versioned compiled notes to deterministic JSONL at
backend/data/output/compiled_context_notes.jsonl. Validate it through an
independent read path and calculate SHA-256.

Add focused scope, temporal, impact, negation, magnitude, invariant,
preservation, serialization, determinism, and supplied-data regression tests.
The supplied 10 notes must match the complete regression contract in Section
18 of the Phase 6 plan.

Do not implement retrieval, similarity scoring, the Evidence Gate, verdicts,
matched-note selection, final explanations, LLM integration, final submission
generation, API endpoints, React, databases, or Docker. Do not change any
Phase 5 candidate decision or preliminary output value.

Run all backend tests, focused Phase 6 coverage, Ruff, prior inspection
commands, candidate generation, and context-note compilation with sensible
timeouts.

When finished, report the 11 items listed in Section 34. Update the Phase 6
checklist, then stop. Do not begin Phase 7.
```
