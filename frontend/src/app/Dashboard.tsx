import { RefreshCw } from 'lucide-react'
import { lazy, Suspense } from 'react'
import type { Anomaly, TimelinePoint, Verdict } from '../api/contracts'
import {
  useAnomalies,
  useAnomaly,
  useEvaluation,
  useMetrics,
  useRootCause,
  useSpotlight,
  useSummary,
  useTimeline,
} from '../api/hooks'
import { Button } from '../components/ui/Button'
import { ErrorState } from '../components/ui/ErrorState'
import { LoadingSkeleton } from '../components/ui/LoadingSkeleton'
import { CostCourtroom } from '../features/courtroom/CostCourtroom'
import { DiagnosticsPanel } from '../features/diagnostics/DiagnosticsPanel'
import { InvestigationSection } from '../features/investigations/InvestigationSection'
import { useInvestigationParams } from '../features/investigations/useInvestigationParams'
import { AttentionSpotlight } from '../features/overview/AttentionSpotlight'
import { OverviewSection } from '../features/overview/OverviewSection'
import { useSnapshotGuard } from '../hooks/useSnapshotGuard'
import { formatFingerprint } from '../lib/format'

const RouteTrendChart = lazy(() =>
  import('../features/timeline/RouteTrendChart').then((module) => ({
    default: module.RouteTrendChart,
  })),
)

export function Dashboard({ onRun }: { onRun: () => void }) {
  const { state, setFilters, select, update } = useInvestigationParams()
  const summary = useSummary()
  const queue = useAnomalies(state.filters)
  const unexplained = useSpotlight('unexplained')
  const partial = useSpotlight('partially_explained', unexplained.isSuccess && unexplained.data.data.items.length === 0)
  const spotlight = unexplained.data?.data.items[0] ?? partial.data?.data.items[0]
  const timelineRoute = state.selectedRoute ?? spotlight?.route
  const detail = useAnomaly(state.selectedRoute, state.selectedWeek)
  const rootCauseEligible = detail.data?.data.verdict === 'unexplained' && detail.data.data.operational_root_cause_available
  const rootCause = useRootCause(state.selectedRoute, state.selectedWeek, Boolean(rootCauseEligible))
  const timeline = useTimeline(timelineRoute, state.filters.weekFrom, state.filters.weekTo)
  const evaluation = useEvaluation(true)
  const metrics = useMetrics()
  const reference = summary.data?.meta.snapshot_id
  const observed = [queue.data?.meta.snapshot_id, unexplained.data?.meta.snapshot_id, partial.data?.meta.snapshot_id, timeline.data?.meta.snapshot_id, detail.data?.meta.snapshot_id, rootCause.data?.meta.snapshot_id, evaluation.data?.meta.snapshot_id, metrics.data?.meta.snapshot_id]
  const guard = useSnapshotGuard(reference, observed)

  const open = (item: Anomaly) => select(item.route, item.week_of)
  const openPoint = (point: TimelinePoint) => { if (timelineRoute && point.candidate) select(timelineRoute, point.week_of) }
  const clear = () => update({ filters: { sortBy: 'vs_own_history_pct', sortOrder: 'desc', page: 1, limit: 20 } })
  const setVerdict = (verdict?: Verdict) => setFilters({ verdict })

  if (summary.isLoading) return <div className="container"><LoadingSkeleton label="Loading trusted summary" /></div>
  if (summary.error) return <div className="container"><ErrorState error={summary.error} onRetry={() => void summary.refetch()} title="Dashboard summary unavailable" /></div>
  if (!summary.data) return null
  if (guard.persistentMismatch) return <div className="container"><ErrorState error={new Error('Snapshot resources did not reconcile after a bounded refresh.')} onRetry={() => window.location.reload()} title="Analysis snapshot mismatch" /></div>
  if (!guard.consistent) return <div className="container banner" role="status"><RefreshCw aria-hidden="true" /> Refreshing analysis snapshot. Mixed-run values are hidden while resources reconcile.</div>

  return <><div className="container"><section className="hero"><div><p className="eyebrow">Evidence-first freight intelligence</p><h2>See the cost surge. Test the context. Trust the verdict.</h2><p className="hero-copy">FreightGuard finds unusual route-week costs and makes every decision auditable—from comparison baselines to rejected evidence.</p></div><div className="trust-stamp"><strong>Evaluation {summary.data.data.evaluation_status}</strong><span>Snapshot {formatFingerprint(reference)} · {summary.data.data.explanation_mode} wording</span><br /><Button variant="ghost" onClick={onRun}>Refresh analysis</Button></div></section><OverviewSection summary={summary.data.data} onVerdict={setVerdict} /><section className="section"><AttentionSpotlight anomaly={spotlight} onInvestigate={open} /></section><InvestigationSection data={queue.data} error={queue.error} loading={queue.isFetching} filters={state.filters} selectedKey={state.selectedRoute && state.selectedWeek ? `${state.selectedRoute}|${state.selectedWeek}` : undefined} onFilters={setFilters} onClear={clear} onSelect={open} onRetry={() => void queue.refetch()} /><section className="section"><Suspense fallback={<LoadingSkeleton label="Loading route visualization" />}><RouteTrendChart data={timeline.data} error={timeline.error} loading={timeline.isLoading} selectedWeek={state.selectedWeek} onCandidate={openPoint} onRetry={() => void timeline.refetch()} /></Suspense></section><DiagnosticsPanel evaluation={evaluation.data} metrics={metrics.data} evaluationError={evaluation.error} metricsError={metrics.error} loading={evaluation.isLoading || metrics.isLoading} onRetry={() => { void evaluation.refetch(); void metrics.refetch() }} /><footer className="footer">Active snapshot <code title={reference ?? ''}>{formatFingerprint(reference)}</code>. FreightGuard displays backend-owned calculations and verdicts without browser-side recomputation.</footer></div><CostCourtroom open={Boolean(state.selectedRoute && state.selectedWeek)} data={detail.data} error={detail.error} loading={detail.isLoading} rootCause={rootCause.data} rootCauseError={rootCause.error} rootCauseLoading={rootCause.isLoading && Boolean(rootCauseEligible)} snapshotId={reference ?? undefined} onClose={() => select()} onRetry={() => void detail.refetch()} onRootCauseRetry={() => void rootCause.refetch()} /></>
}
