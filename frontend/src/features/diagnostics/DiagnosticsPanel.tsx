import { ChevronDown, Clock3, Database, ShieldCheck } from 'lucide-react'
import type { EvaluationEnvelope, MetricsEnvelope } from '../../api/contracts'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { ErrorState } from '../../components/ui/ErrorState'
import { LoadingSkeleton } from '../../components/ui/LoadingSkeleton'
import { formatCurrency, formatDuration, formatFingerprint, formatInteger, sentenceCase } from '../../lib/format'

export function DiagnosticsPanel({ evaluation, metrics, evaluationError, metricsError, loading, onRetry }: { evaluation?: EvaluationEnvelope; metrics?: MetricsEnvelope; evaluationError: unknown; metricsError: unknown; loading: boolean; onRetry: () => void }) {
  if (loading && !evaluation && !metrics) return <LoadingSkeleton label="Loading diagnostics" />
  return <section className="section" aria-labelledby="diagnostics-heading"><div className="section-heading"><div><p className="eyebrow">Trust and operations</p><h2 id="diagnostics-heading">Evaluation & run diagnostics</h2><p>Technical evidence stays available without crowding the investigation.</p></div></div><div className="diagnostics-grid">
    {evaluationError ? <ErrorState error={evaluationError} onRetry={onRetry} title="Evaluation unavailable" /> : evaluation && <EvaluationSummary data={evaluation} />}
    {metricsError ? <ErrorState error={metricsError} onRetry={onRetry} title="Run metrics unavailable" /> : metrics && <RunMetrics data={metrics} />}
  </div></section>
}

function EvaluationSummary({ data }: { data: EvaluationEnvelope }) {
  const report = data.data.report
  const blocking = report.checks.filter((check) => check.blocking)
  const passed = blocking.filter((check) => check.status === 'pass').length
  const domains = [...new Set(report.checks.map((check) => check.domain))]
  return <Card className="panel"><div className="section-heading"><div><ShieldCheck aria-hidden="true" /><h3>Evaluation</h3></div><Badge tone={report.overall_status}>{report.overall_status.toUpperCase()}</Badge></div><ul className="metric-list"><li className="metric-row"><span>Blocking checks</span><strong>{passed} / {blocking.length} passed</strong></li><li className="metric-row"><span>Reproducibility</span><strong>{report.reproducibility.overall_reproducible ? 'Reproducible' : 'Failed'}</strong></li><li className="metric-row"><span>Formal runs</span><strong>{report.run_count}</strong></li><li className="metric-row"><span>Report fingerprint</span><code title={data.data.report_sha256}>{formatFingerprint(data.data.report_sha256)}</code></li></ul><details><summary><ChevronDown size={16} /> View checks by domain</summary>{domains.map((domain) => <div key={domain}><h4>{sentenceCase(domain)}</h4><ul className="metric-list">{report.checks.filter((check) => check.domain === domain).map((check) => <li className="metric-row" key={check.check_id}><span>{check.description}</span><Badge tone={check.status}>{sentenceCase(check.status)}{check.blocking ? ' · blocking' : ''}</Badge></li>)}</ul></div>)}</details></Card>
}

function RunMetrics({ data }: { data: MetricsEnvelope }) {
  const metrics = data.data
  return <Card className="panel"><div className="section-heading"><div><Clock3 aria-hidden="true" /><h3>Latest successful run</h3></div><Badge tone={metrics.latest_attempt.state === 'failed' ? 'danger' : 'pass'}>{sentenceCase(metrics.latest_attempt.state)}</Badge></div><ul className="metric-list"><li className="metric-row"><span>Total duration</span><strong>{formatDuration(metrics.total_duration_ms)}</strong></li><li className="metric-row"><span>Retrieval hits</span><strong>{formatInteger(metrics.retrieval_hit_count)}</strong></li><li className="metric-row"><span>Hosted-model calls</span><strong>{formatInteger(metrics.hosted_model_call_count)}</strong></li><li className="metric-row"><span>Tokens</span><strong>{metrics.input_tokens == null || metrics.output_tokens == null ? 'Not available' : `${metrics.input_tokens} in / ${metrics.output_tokens} out`}</strong></li><li className="metric-row"><span>Estimated cost</span><strong>{formatCurrency(metrics.estimated_cost_usd)}</strong></li><li className="metric-row"><span>Cache</span><strong>{metrics.cache_hits} hits / {metrics.cache_misses} misses</strong></li><li className="metric-row"><span>Fallbacks</span><strong>{metrics.fallback_count}</strong></li></ul><details><summary><Database size={16} /> Stage durations and fingerprints</summary><ul className="metric-list">{Object.entries(metrics.stage_durations_ms).map(([stage, value]) => <li className="metric-row" key={stage}><span>{sentenceCase(stage)}</span><strong>{formatDuration(value)}</strong></li>)}</ul><p>Configuration <code title={metrics.configuration_fingerprint}>{formatFingerprint(metrics.configuration_fingerprint)}</code></p>{metrics.artifact_fingerprints.map((artifact) => <p key={artifact.relative_path}>{artifact.relative_path}: <code title={artifact.sha256}>{formatFingerprint(artifact.sha256)}</code></p>)}</details></Card>
}
