# FreightGuard evaluation report

## Executive result

**Overall: PASS**

Mode: `template`  
Formal runs: 3  
Configuration fingerprint: `ebea8117a90d5c2b67180e6130303f614b5723cf95ad1294077a8031e96c4706`

| Domain | Status |
|---|---|
| baseline_correctness | PASS |
| candidate_detection | PASS |
| context_compilation | PASS |
| evidence_gate | PASS |
| explanation_grounding | PASS |
| input_integrity | PASS |
| investigation_assistant | PASS |
| metamorphic_invariants | PASS |
| operational_root_cause | PASS |
| output_contract | PASS |
| reproducibility | PASS |
| retrieval_quality | PASS |
| weekly_analytics | PASS |

## Blocking failures

None.

## Input and environment fingerprints

| Input | Bytes | SHA-256 |
|---|---:|---|
| backend/data/input/shipment_records.csv | 259523 | `1a2b4d66c4dc694111ba37b966486b5b0650df9ec8687402f3434117b140f4b6` |
| backend/data/input/context_notes.csv | 1715 | `875c57a896ac3dfac0f712f8865b287bb5d2bd5423d26e798297b74dce87e6dc` |
| backend/data/input/sample_output_format_v2.csv | 903 | `1ea902faca37bef6816e0878dc17bdb509a88f9ff9d4f101373e3af03994201f` |

Python: `3.12.6 (tags/v3.12.6:a4a2d2b, Sep  6 2024, 20:11:23) [MSC v.1940 64 bit (AMD64)]`  
OS/architecture: `Windows / AMD64`  
Timezone/locale: `UTC / LC_COLLATE=C;LC_CTYPE=English_India.1252;LC_MONETARY=C;LC_NUMERIC=C;LC_TIME=C`

## Mathematical regression summary

25/25 checks passed.

## Candidate and verdict summary

14/14 checks passed.

## Retrieval metrics

| Metric | Value | Target |
|---|---:|---:|
| retrieval.hybrid_mean_reciprocal_rank | 0.28888888888888886 | informational - |
| retrieval.hybrid_recall_at_1 | 0.2 | informational 1.0 |
| retrieval.hybrid_recall_at_3 | 0.4666666666666667 | informational 1.0 |
| retrieval.hybrid_recall_at_5 | 0.4666666666666667 | informational 1.0 |
| retrieval.structured_union_recall | 1.0 | eq 1.0 |

## Evidence safety metrics

| Metric | Value | Target |
|---|---:|---:|
| evidence.accepted_evidence_precision | 1.0 | eq 1.0 |
| evidence.accepted_evidence_recall | 1.0 | eq 1.0 |
| evidence.false_clearance_rate | 0.0 | eq 0.0 |
| evidence.full_evidence_precision | 1.0 | eq 1.0 |
| evidence.full_evidence_recall | 1.0 | eq 1.0 |
| evidence.rejected_evidence_accuracy | 1.0 | eq 1.0 |
| evidence.selected_note_accuracy | 1.0 | eq 1.0 |
| evidence.unsafe_evidence_acceptance_rate | 0.0 | eq 0.0 |
| evidence.verdict_accuracy | 1.0 | eq 1.0 |

## Explanation-grounding metrics

| Metric | Value | Target |
|---|---:|---:|
| explanation.authorized_citation_rate | 1.0 | eq 1.0 |
| explanation.decision_invariance_rate | 1.0 | eq 1.0 |
| explanation.fallback_coverage_rate | 1.0 | eq 1.0 |
| explanation.identity_binding_accuracy | 1.0 | eq 1.0 |
| explanation.unsupported_note_id_rate | 0.0 | eq 0.0 |
| explanation.unsupported_numeric_claim_rate | 0.0 | eq 0.0 |
| explanation.verdict_language_consistency_rate | 1.0 | eq 1.0 |

## Investigation-assistant metrics

| Metric | Value | Target |
|---|---:|---:|
| assistant.ambiguity_clarification_rate | 100.0 | gte 100 |
| assistant.average_citation_count | 3.875 | informational - |
| assistant.average_tool_count | 0.65 | informational - |
| assistant.canonical_mutation_rate | 0.0 | eq 0 |
| assistant.citation_validity_rate | 100.0 | gte 100 |
| assistant.fact_grounding_rate | 100.0 | gte 100 |
| assistant.intent_accuracy | 100.0 | gte 100 |
| assistant.plan_validity_rate | 100.0 | gte 100 |
| assistant.prohibited_tool_execution_rate | 0.0 | eq 0 |
| assistant.prompt_injection_escape_rate | 0.0 | eq 0 |
| assistant.provider_call_count | 0 | eq 0 |
| assistant.snapshot_consistency_rate | 100.0 | gte 100 |
| assistant.tool_allowlist_compliance | 100.0 | gte 100 |
| assistant.unsupported_honesty_rate | 100.0 | gte 100 |

## Output-contract results

16/16 checks passed.

## Metamorphic results

7/7 checks passed.

## Three-run reproducibility table

| Run | Exit | Duration ms | Rows | Columns | Final SHA-256 |
|---|---:|---:|---:|---:|---|
| run_01 | 0 | 12713 | 19 | 8 | `73fad5f7244fe4e016dee055b96da98d90107da93fdd46d09b092a1975d678f7` |
| run_02 | 0 | 11893 | 19 | 8 | `73fad5f7244fe4e016dee055b96da98d90107da93fdd46d09b092a1975d678f7` |
| run_03 | 0 | 11740 | 19 | 8 | `73fad5f7244fe4e016dee055b96da98d90107da93fdd46d09b092a1975d678f7` |

## Artifact hashes

- `final_submission.csv`: identical — 73fad5f7244fe4e016dee055b96da98d90107da93fdd46d09b092a1975d678f7, 73fad5f7244fe4e016dee055b96da98d90107da93fdd46d09b092a1975d678f7, 73fad5f7244fe4e016dee055b96da98d90107da93fdd46d09b092a1975d678f7
- `explanation_generation_audit.jsonl`: identical — 62a7db940c895dc306d56848c65a950990f88e200a641d4f00178879e3722dea, 62a7db940c895dc306d56848c65a950990f88e200a641d4f00178879e3722dea, 62a7db940c895dc306d56848c65a950990f88e200a641d4f00178879e3722dea
- `operational_root_causes.json`: identical — dd584659bea3e9bac3455eecd946f4f3911ae57a49a829711ced064ab6149968, dd584659bea3e9bac3455eecd946f4f3911ae57a49a829711ced064ab6149968, dd584659bea3e9bac3455eecd946f4f3911ae57a49a829711ced064ab6149968

## Performance observations

Durations are informational; the configured subprocess timeout is the only blocking performance threshold.

## Limitations and skipped non-blocking checks

Dense-rank floating-point values are observed but are not blocking when structured recall preserves all accepted evidence. Peak memory is not measured because the project has no established profiler.

## Exact rerun command

```text
cd backend
python -m scripts.evaluate_pipeline --runs 3 --mode template
```
