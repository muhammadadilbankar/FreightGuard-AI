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

## ADR-021: Require positive own-history movement before candidate flagging

- **Status:** Accepted
- **Context:** A route can be expensive relative to peers while falling versus its
  own history, but the challenge asks for rising costs.
- **Decision:** Require an available, strictly positive own-history deviation before
  either threshold component can produce a candidate.
- **Consequences:** Missing, zero, or negative own movement cannot be flagged solely
  by a high peer comparison.

## ADR-022: Use inclusive configurable thresholds on own or peer deviation

- **Status:** Accepted
- **Context:** The challenge defines baselines but no anomaly threshold.
- **Decision:** Inject one finite non-negative threshold, defaulting to 20 percent,
  and treat equality on either available comparison as a breach.
- **Consequences:** Sensitivity is auditable and configurable without changing rule
  code; own and peer boundaries have identical semantics.

## ADR-023: Apply thresholds before display rounding

- **Status:** Accepted
- **Context:** A value below 20 percent can display as `+20.0%` at one decimal.
- **Decision:** Calculate and evaluate numeric deviations at full precision, then
  format only the preliminary output fields.
- **Consequences:** Presentation rounding cannot change a candidate decision.

## ADR-024: Export candidate rows only using the exact contract

- **Status:** Accepted
- **Context:** The preliminary artifact must match the challenge header without
  implying that every weekly row is anomalous.
- **Decision:** Export only `candidate_anomaly = True` rows using the authoritative
  Phase 2 eight-column contract and stable route/week ordering.
- **Consequences:** The Phase 5 CSV is compact, deterministic, and directly
  reconcilable to the canonical candidate set.

## ADR-025: Keep preliminary candidates flagged until evidence evaluation

- **Status:** Accepted
- **Context:** Phase 5 has not searched or validated context notes.
- **Decision:** Set every candidate to `Yes`, leave `matched_note_id` blank, and use
  wording that explicitly says context review is pending.
- **Consequences:** The artifact makes no unsupported claim about evidence and cannot
  be mistaken for a final evidence-reviewed verdict.

## ADR-026: Validate generated CSV through an independent round trip

- **Status:** Accepted
- **Context:** Correct in-memory columns do not prove that quoting, blank cells, or
  serialized records satisfy the file contract.
- **Decision:** Read the written CSV through the standard library and validate its
  exact header, field counts, row count, order, fixed Phase 5 fields, numeric costs,
  ISO dates, and non-empty comparisons.
- **Consequences:** Serialization failures stop the command instead of leaving a
  misleading artifact; commas, quotes, and embedded newlines remain safe.

## ADR-027: Compile context notes deterministically before retrieval

- **Status:** Accepted
- **Context:** Retrieval and evidence validation need stable structured claims rather
  than repeatedly interpreting free text.
- **Decision:** Compile notes once through explicit scope, time, event, impact,
  negation, and magnitude rules before any candidate-specific retrieval.
- **Consequences:** Later phases receive reproducible typed inputs without embedding
  candidate matching or verdict logic in the compiler.

## ADR-028: Preserve unknown transport-cost impact as null

- **Status:** Accepted
- **Context:** An unstated cost effect is not equivalent to an explicit no-impact
  statement.
- **Decision:** Derive `affects_transport_cost = null` for `not_stated` and
  `unknown`, reserving false for explicit negation or normal/stable operations.
- **Consequences:** Phase 7 can reject unsupported claims while retaining the reason
  that support is unavailable.

## ADR-029: Give explicit negation precedence over positive keywords

- **Status:** Accepted
- **Context:** Notes can mention compliance costs or disruptions while explicitly
  saying freight rates did not change.
- **Decision:** Evaluate no-rate-change, no-material-impact, and stable-operation
  rules before positive cost rules; retain irreconcilable claims as unknown.
- **Consequences:** Incidental positive words cannot override an explicit negation.

## ADR-030: Represent effective intervals as inclusive typed ranges

- **Status:** Accepted
- **Context:** Candidate-week overlap requires unambiguous temporal boundaries.
- **Decision:** Compile explicit ranges, weeks, calendar quarters, and continuing
  states into inclusive dates, using null only for an open-ended end date.
- **Consequences:** Unsupported wording falls back conservatively to the source date
  with a warning instead of inventing a long duration.

## ADR-031: Preserve source text with every structured claim

- **Status:** Accepted
- **Context:** Extracted fields must remain auditable against their exact source.
- **Decision:** Store the original Phase 2 note text and normalized source metadata
  unchanged beside every compiled claim.
- **Consequences:** Later review can trace each field without relying on a summary or
  lossy transformation.

## ADR-032: Serialize compiled notes as versioned deterministic JSONL

- **Status:** Accepted
- **Context:** Compiled claims contain arrays, booleans, nulls, dates, and warnings
  that are awkward to represent safely in CSV.
- **Decision:** Write schema version `1.0` as compact UTF-8 JSONL in note-ID order,
  atomically replace the artifact, and validate it through a typed readback.
- **Consequences:** Identical inputs produce identical bytes and Phase 7 receives a
  format that preserves domain types.

## ADR-033: Keep evidence acceptance outside the note compiler

- **Status:** Accepted
- **Context:** Structured note meaning alone does not establish relevance to a
  particular anomaly.
- **Decision:** Phase 6 never retrieves notes, selects a match, changes a candidate
  flag, or issues an evidence verdict.
- **Consequences:** Phase 7 remains the sole owner of route, date, direction, impact,
  and explanatory-scope acceptance.

## ADR-034: Use hybrid sparse and dense retrieval for note discovery

- **Status:** Accepted
- **Decision:** Search compiled notes with deterministic TF-IDF and local semantic
  embeddings.
- **Consequences:** Exact wording and semantic similarity can both aid discovery,
  while neither channel has verdict authority.

## ADR-035: Fuse discovery channels with deterministic Reciprocal Rank Fusion

- **Status:** Accepted
- **Decision:** Combine one-based sparse and dense ranks using configured weighted
  Reciprocal Rank Fusion and stable note-ID tie-breaking.
- **Consequences:** Incomparable raw score scales cannot distort fusion, and repeated
  runs preserve ordering.

## ADR-036: Union retrieval with structured route/time recall

- **Status:** Accepted
- **Decision:** Add every exact-route or global note whose inclusive interval
  overlaps the candidate week to the fused top-k set.
- **Consequences:** A valid low-similarity note cannot be lost before hard evidence
  validation; no-impact notes remain visible for audit.

## ADR-037: Give the Evidence Gate sole authority over verdicts

- **Status:** Accepted
- **Decision:** Validate compiled consistency, dataset scope, route direction, time,
  explicit transport-cost impact, direction, negation, and explanatory scope with
  deterministic rules.
- **Consequences:** Similarity scores can affect discovery order but cannot accept an
  invalid claim or clear a candidate.

## ADR-038: Keep global evidence partial for peer-driven anomalies

- **Status:** Accepted
- **Decision:** Treat applicable global increases as partial when the peer threshold
  was breached; use the configured magnitude tolerance for own-only anomalies.
- **Consequences:** Market-wide context cannot explain a route-specific peer premium.

## ADR-039: Populate matched note ID only for full justification

- **Status:** Accepted
- **Decision:** Select exactly one deterministic full-evidence note for justified
  decisions and leave `matched_note_id` blank for partial and unexplained results.
- **Consequences:** The challenge output never presents partial context as conclusive.

## ADR-040: Preserve rejected-note reasons in a deterministic audit trail

- **Status:** Accepted
- **Decision:** Write every assessed note, retrieval provenance, gate outcome, and
  sorted rejection code to versioned, atomically written JSONL.
- **Consequences:** Reviewers can reconstruct why each discovered note was accepted
  or rejected without changing the eight-column submission contract.

## ADR-041: Use local pinned embeddings without a vector database

- **Status:** Accepted
- **Decision:** Prepare one exact Sentence Transformers revision explicitly and load
  its repository-local files lazily on CPU with remote custom code disabled.
- **Consequences:** Evidence review runs offline after preparation, tests inject fake
  providers, and the small note corpus needs no persistent vector infrastructure.

## ADR-042: Restrict model authority to explanation wording

- **Status:** Accepted
- **Decision:** Treat every Phase 7 number, verdict, flag, and evidence identifier as
  immutable; a model may supply only validated reason wording and citations.
- **Consequences:** Model behavior cannot change the canonical investigation result.

## ADR-043: Generate only from Phase 7 validated evidence packets

- **Status:** Accepted
- **Decision:** Build minimal requests exclusively from selected and accepted
  supporting evidence in `ValidatedEvidencePacket` objects.
- **Consequences:** Rejected notes and retrieval internals never enter a prompt.

## ADR-044: Skip model calls for unexplained candidates

- **Status:** Accepted
- **Decision:** Render the unexplained template directly when no evidence passed.
- **Consequences:** The system avoids speculative causation and unnecessary cost.

## ADR-045: Require structured output plus deterministic post-validation

- **Status:** Accepted
- **Decision:** Use a strict Pydantic response schema and independently validate
  identity, verdict, citations, numbers, wording, format, and length.
- **Consequences:** Schema compliance alone cannot bypass grounding controls.

## ADR-046: Enforce note-ID and numeric-claim allowlists

- **Status:** Accepted
- **Decision:** Reject cited or prose-mentioned note IDs outside the packet and
  numeric claims absent from approved display facts or evidence magnitudes.
- **Consequences:** Fabricated citations and quantitative details cannot reach CSV.

## ADR-047: Fall back without repair prompting on invalid content

- **Status:** Accepted
- **Decision:** Use the verdict-aware deterministic template immediately after a
  refusal or content-validation failure; retry only transient transport failures.
- **Consequences:** Unsafe output never becomes new prompt context or multiplies calls.

## ADR-048: Cache only fully validated model output by content hash

- **Status:** Accepted
- **Decision:** Key cached provider output by prompt, provider/model, request, and
  response-schema identity, and revalidate it before reuse.
- **Consequences:** Cache invalidation is automatic and corrupt entries are untrusted.

## ADR-049: Support template, live, and replay generation modes

- **Status:** Accepted
- **Decision:** Default to offline templates, allow cache-first live generation, and
  provide network-free cache-only replay.
- **Consequences:** CI and demos remain safe while production wording is optional.

## ADR-050: Keep pricing configuration external and date-stamped

- **Status:** Accepted
- **Decision:** Calculate estimates with `Decimal` and configured per-million-token
  rates tied to a pricing snapshot date.
- **Consequences:** Missing rates yield unavailable cost instead of stale fake values.

## ADR-051: Use explicit blocking gates instead of an opaque overall score

- **Status:** Accepted
- **Decision:** Phase 9 passes only when every blocking check and metric target passes.
- **Consequences:** A high score cannot conceal a safety or reproducibility failure.

## ADR-052: Evaluate production outputs through independent read paths

- **Status:** Accepted
- **Decision:** Recompute mathematical properties and parse final CSV bytes independently of production validators.
- **Consequences:** Evaluation cannot pass merely by trusting pipeline summaries.

## ADR-053: Treat false anomaly clearance as a zero-tolerance safety metric

- **Status:** Accepted
- **Decision:** Any incorrectly justified anomaly or unsafe accepted note fails formal evaluation.
- **Consequences:** Retrieval quality cannot compensate for an evidence-safety failure.

## ADR-054: Test the evaluator with deliberate output corruption

- **Status:** Accepted
- **Decision:** Mutate headers, fields, flags, note IDs, row cardinality, uniqueness, and quoting in valid CSV copies.
- **Consequences:** A negative control that escapes detection fails the evaluator itself.

## ADR-055: Run reproducibility in three fresh isolated processes

- **Status:** Accepted
- **Decision:** Formal evaluation invokes the complete Phase 8 command three times with isolated output directories and explicit timeouts.
- **Consequences:** Hidden process state, import order, and output-path coupling become observable.

## ADR-056: Restrict formal reproducibility to template or frozen replay mode

- **Status:** Accepted
- **Decision:** Live provider generation is forbidden in formal evaluation.
- **Consequences:** Formal output never depends on network access or fresh model sampling.

## ADR-057: Separate canonical artifact equality from operational telemetry

- **Status:** Accepted
- **Decision:** Byte-compare canonical CSV output while validating latency and audit metadata semantically.
- **Consequences:** Legitimate timing variation cannot create a false reproducibility failure.

## ADR-058: Fingerprint inputs, output-affecting configuration, and environment

- **Status:** Accepted
- **Decision:** Record SHA-256 input hashes, a canonical non-secret configuration hash, dependency versions, and safe environment identity.
- **Consequences:** A report states precisely which data and deterministic settings it evaluated without exposing credentials or personal paths.

## ADR-059: Publish one immutable in-memory snapshot atomically

- **Status:** Accepted
- **Decision:** Build all Phase 2–9 results privately and replace a single snapshot reference only after every invariant and evaluation gate passes.
- **Consequences:** Concurrent reads belong wholly to the old or new run; a failed refresh preserves the last good result.

## ADR-060: Enforce one analysis run and one API worker

- **Status:** Accepted
- **Decision:** Reject overlapping run attempts with `409` and configure Uvicorn for exactly one worker.
- **Consequences:** Process-local coordination is deterministic without pretending to provide distributed locking.

## ADR-061: Bind API publication to the existing formal Phase 9 report

- **Status:** Accepted
- **Decision:** Require a passing three-run report whose input fingerprints, output-affecting configuration fingerprint, and final CSV hash match the requested run.
- **Consequences:** A normal API refresh avoids launching three subprocesses while it cannot publish content outside the proven evaluation envelope.

## ADR-062: Keep transport contracts separate from domain models

- **Status:** Accepted
- **Decision:** Serialize explicit Pydantic wire models from immutable application read models.
- **Consequences:** HTTP evolution cannot silently weaken analytical contracts or expose internal provider data.

## ADR-063: Serve exact validated export bytes

- **Status:** Accepted
- **Decision:** Store the trusted CSV path and hash in the snapshot, recheck integrity on download, and support SHA-256 ETags.
- **Consequences:** Export never reconstructs or rounds canonical rows in an API route.

## ADR-064: Generate frontend contracts from OpenAPI

- **Status:** Accepted
- **Decision:** Generate TypeScript schema types from the running Phase 10 OpenAPI
  document and keep all HTTP access behind one typed transport layer.
- **Consequences:** Contract drift is reviewable and feature components do not invent
  response shapes.

## ADR-065: Keep canonical analysis out of the browser

- **Status:** Accepted
- **Decision:** Render backend-provided baselines, deviations, evidence gates,
  verdicts, evaluation results, and export bytes without browser-side recomputation.
- **Consequences:** Presentation changes cannot silently create a second decision
  engine.

## ADR-066: Refuse mixed analysis snapshots

- **Status:** Accepted
- **Decision:** Use the summary snapshot as the reference, invalidate all snapshot
  query families once on disagreement, and show a blocking error if they do not
  converge.
- **Consequences:** A dashboard never combines old and new run values into an
  apparently coherent investigation.

## ADR-067: Store investigation state in the URL

- **Status:** Accepted
- **Decision:** Keep filters, sorting, pagination, and the selected route-week in
  validated query parameters while TanStack Query owns remote server state.
- **Consequences:** Investigations are shareable and reload-safe without persisting
  canonical data in browser storage.

## ADR-068: Operational leads cannot modify canonical Evidence Gate verdicts

- **Status:** Accepted
- **Decision:** Compute deterministic operational leads only after the Evidence
  Gate. They cannot select notes, clear flags, or change a canonical verdict.
- **Consequences:** Shipment patterns remain descriptive investigation aids.

## ADR-069: Keep transporter and material decompositions independent

- **Status:** Accepted
- **Decision:** Each lens separately partitions the same own-history cost gap with
  symmetric mix/rate and explicit category entry/exit effects.
- **Consequences:** Both lenses reconstruct the gap but must never be added together.
