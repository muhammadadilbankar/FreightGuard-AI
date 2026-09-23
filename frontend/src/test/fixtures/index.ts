import type {
  Anomaly,
  AnomalyEnvelope,
  AnomalyListEnvelope,
  EvaluationEnvelope,
  Health,
  MetricsEnvelope,
  RunEnvelope,
  RootCauseEnvelope,
  SummaryEnvelope,
  TimelineEnvelope,
} from '../../api/contracts'

export const snapshotId = 'snapshot-test-a'
export const healthReady: Health = { status: 'ok', ready: true, service: 'FreightGuard AI API', version: '0.10.0', run_state: 'succeeded', has_snapshot: true, snapshot_id: snapshotId }
export const anomaly: Anomaly = {
  operational_root_cause_available: true,
  candidate_key: 'Test-Route|2024-01-08', route: 'Test-Route', route_type: 'Short', week_of: '2024-01-08', cost_per_tonne_km: 2.5,
  own_history_baseline: 2, peer_baseline: 2.1, vs_own_history_pct: 25, vs_similar_routes_pct: 19.05,
  history_weeks_used: 8, peer_routes_used: 2, own_threshold_breached: true, peer_threshold_breached: false,
  trigger: 'own_history', verdict: 'unexplained', flagged: 'Yes', matched_note_id: null, supporting_note_ids: [], decision_code: 'unexplained',
  reason: 'No supplied context passed every required gate.', explanation_source: 'template', fallback_used: false,
  evidence: [{ note_id: 'TEST-NOTE', evidence_level: 'rejected', role: 'rejected', rejection_codes: ['date_no_overlap'], original_text: 'A test-only note outside the candidate week.', scope_type: 'route', applies_to_routes: ['Test-Route'], effective_from: '2023-01-01', effective_to: '2023-01-07', event_type: 'weather_disruption', impact_direction: 'increase', affects_transport_cost: true, magnitude_text: null, gate_results: [{ gate: 'route', status: 'pass', reason_code: null, reason: 'The deterministic Evidence Gate passed this check.' }, { gate: 'date', status: 'fail', reason_code: 'date_no_overlap', reason: 'The deterministic Evidence Gate rejected this check.' }] }],
}
const meta = { schema_version: '1.0' as const, snapshot_id: snapshotId, pagination: null }
export const summary: SummaryEnvelope = { data: { operational_root_causes_available: 0, shipment_count: 100, route_count: 2, route_type_count: 1, weekly_record_count: 20, candidate_count: 1, justified_count: 0, partially_explained_count: 0, unexplained_count: 1, analysis_from: '2024-01-01', analysis_to: '2024-03-04', anomaly_threshold_percent: 20, explanation_mode: 'template', evaluation_status: 'pass', final_csv_sha256: 'a'.repeat(64), run_state: 'succeeded' }, meta }
export const anomalyList: AnomalyListEnvelope = { data: { items: [anomaly] }, meta: { ...meta, pagination: { total: 1, limit: 20, offset: 0, has_more: false } } }
export const anomalyDetail: AnomalyEnvelope = { data: anomaly, meta }
const rootContribution = { category: 'Carrier A', current_shipment_count: 2, reference_shipment_count: 8, reference_weeks_present: 4, current_tonne_km_share: 0.6, reference_mean_tonne_km_share: 0.4, current_cost_per_tonne_km: 3, reference_mean_cost_per_tonne_km: 2, mix_effect: 0.2, rate_effect: 0.4, entry_effect: 0, exit_effect: 0, net_contribution: 0.6, absolute_effect_share_pct: 100, direction: 'increases_gap' as const, support_level: 'strong' as const, caveats: [] }
const rootLens = (lens: 'transporter' | 'material') => ({ lens, target_gap: 0.6, reconstructed_gap: 0.6, reconstruction_error: 0, contributions: [{ ...rootContribution, category: lens === 'transporter' ? 'Carrier A' : 'Steel' }], leads: [], offsets: [] })
export const rootCause: RootCauseEnvelope = { data: { schema_version: '1.0', candidate_key: anomaly.candidate_key, route: anomaly.route, route_type: anomaly.route_type, week_of: anomaly.week_of, canonical_verdict: 'unexplained', availability: 'available', reference_weeks: ['2024-01-01'], reference_week_count: 1, support_level: 'limited', current_cost_per_tonne_km: 2.6, own_history_baseline: 2, target_gap: 0.6, transporter: rootLens('transporter'), material: rootLens('material'), operational_metrics: [{ metric: 'shipment_count', unit: 'shipments', current_value: 3, reference_mean: 2, absolute_change: 1, percentage_change: 50, highlighted: true, interpretation: 'Descriptive only.' }], caveats: ['The lenses must not be added together.'] }, meta }
export const timeline: TimelineEnvelope = { data: { route: anomaly.route, points: [{ week_of: anomaly.week_of, route_type: anomaly.route_type, cost_per_tonne_km: anomaly.cost_per_tonne_km, own_history_baseline: anomaly.own_history_baseline, peer_baseline: anomaly.peer_baseline, vs_own_history_pct: anomaly.vs_own_history_pct, vs_similar_routes_pct: anomaly.vs_similar_routes_pct, history_weeks_used: 8, peer_routes_used: 2, candidate: true, verdict: anomaly.verdict }] }, meta }
export const evaluation = { data: { report: { schema_version: '1.0', overall_status: 'pass', evaluation_mode: 'template', run_count: 3, environment: { python: 'test', implementation: 'test', operating_system: 'test', architecture: 'test', timezone: 'UTC', locale: 'C', dependency_versions: {}, dependency_lock_sha256: null, embedding_model: 'test', embedding_revision: 'test', explanation_mode: 'template', prompt_version: 'test', provider_identity: 'template', git_commit: null, dirty_worktree: false }, inputs: [], configuration_fingerprint: 'b'.repeat(64), checks: [{ check_id: 'test', domain: 'output_contract', description: 'Output contract passes', blocking: true, status: 'pass', expected: null, actual: null, tolerance: null, details: [] }], metrics: [], reproducibility: { formal: true, run_count: 3, runs: [], comparisons: [], overall_reproducible: true }, artifacts: [] }, report_sha256: 'c'.repeat(64) }, meta } as EvaluationEnvelope
export const metrics = { data: { stage_durations_ms: { analytics: 10 }, total_duration_ms: 100, row_counts: { candidates: 1 }, retrieval_hit_count: 2, explanation_request_count: 0, hosted_model_call_count: 0, input_tokens: null, output_tokens: null, estimated_cost_usd: null, cache_hits: 0, cache_misses: 0, fallback_count: 0, input_fingerprints: [], configuration_fingerprint: 'b'.repeat(64), artifact_fingerprints: [], latest_attempt: { state: 'succeeded', attempt_id: 'attempt', started_at: null, finished_at: null, latest_snapshot_id: snapshotId, failure_code: null, failure_message: null, previous_snapshot_available: true } }, meta } as MetricsEnvelope
export const runResponse: RunEnvelope = { data: { attempt_id: 'attempt-2', snapshot_id: snapshotId, run_state: 'succeeded', started_at: '2024-01-01T00:00:00Z', finished_at: '2024-01-01T00:00:01Z', duration_ms: 1000, shipment_count: 100, weekly_record_count: 20, candidate_count: 1, justified_count: 0, partially_explained_count: 0, unexplained_count: 1, evaluation_status: 'pass', final_csv_sha256: 'a'.repeat(64), replaced_previous_snapshot: false }, meta }
