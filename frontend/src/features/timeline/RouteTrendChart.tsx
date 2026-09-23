import { Activity } from 'lucide-react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { TimelineEnvelope, TimelinePoint } from '../../api/contracts'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { LoadingSkeleton } from '../../components/ui/LoadingSkeleton'
import { formatCostPerTonneKm, formatDate, formatPercent } from '../../lib/format'

export function RouteTrendChart({ data, error, loading, selectedWeek, onCandidate, onRetry }: { data?: TimelineEnvelope; error: unknown; loading: boolean; selectedWeek?: string; onCandidate: (point: TimelinePoint) => void; onRetry: () => void }) {
  if (loading && !data) return <LoadingSkeleton label="Loading route timeline" />
  if (error) return <ErrorState error={error} onRetry={onRetry} title="Route trend unavailable" />
  const points = data?.data.points ?? []
  if (!points.length) return <EmptyState title="No route selected" message="Open a candidate to view its complete route history." />
  const selected = points.find((point) => point.week_of === selectedWeek)
  return (
    <Card className="chart-card">
      <div className="section-heading"><div><p className="eyebrow"><Activity size={15} /> Route trend</p><h2>{data?.data.route}</h2><p>Weekly cost with own-history and same-week peer baselines</p></div></div>
      <div className="chart-wrap" aria-label={`Cost trend for ${data?.data.route}`}>
        <ResponsiveContainer width="100%" height="100%"><LineChartAccessible data={points} selectedWeek={selectedWeek} onCandidate={onCandidate} /></ResponsiveContainer>
      </div>
      <div className="chart-alternative" aria-live="polite">{selected ? <>Selected {formatDate(selected.week_of)}: cost {formatCostPerTonneKm(selected.cost_per_tonne_km)}, own deviation {formatPercent(selected.vs_own_history_pct)}, peer deviation {formatPercent(selected.vs_similar_routes_pct)}. Verdict {selected.verdict ?? 'not a candidate'}.</> : 'Select an anomaly to emphasize its week. Candidate weeks are shown with markers.'}</div>
    </Card>
  )
}

function LineChartAccessible({ data, selectedWeek, onCandidate }: { data: TimelinePoint[]; selectedWeek?: string; onCandidate: (point: TimelinePoint) => void }) {
  return <LineChart data={data} margin={{ top: 10, right: 20, left: 4, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" stroke="#d8dddc" /><XAxis dataKey="week_of" minTickGap={45} tickFormatter={(value: string) => value.slice(2, 7)} /><YAxis width={58} tickFormatter={(value: number) => `₹${value.toFixed(1)}`} /><Tooltip content={({ active, payload }) => active && payload?.[0] ? <ChartTooltip point={payload[0].payload as TimelinePoint} /> : null} /><Legend /><Line type="linear" dataKey="cost_per_tonne_km" name="Weekly cost" stroke="#0088ad" strokeWidth={3} dot={{ r: 1.5 }} isAnimationActive={false} connectNulls={false} /><Line type="linear" dataKey="own_history_baseline" name="Own-history baseline" stroke="#7a5ea8" strokeDasharray="8 5" dot={false} isAnimationActive={false} connectNulls={false} /><Line type="linear" dataKey="peer_baseline" name="Peer baseline" stroke="#b46a00" strokeDasharray="3 5" dot={false} isAnimationActive={false} connectNulls={false} />{data.filter((point) => point.candidate).map((point) => <ReferenceDot key={point.week_of} x={point.week_of} y={point.cost_per_tonne_km} r={5} fill="#c44436" stroke="#fff" onClick={() => onCandidate(point)} />)}{selectedWeek && <ReferenceLine x={selectedWeek} stroke="#c44436" strokeWidth={2} label="Selected" />}</LineChart>
}

function ChartTooltip({ point }: { point: TimelinePoint }) {
  return <div className="card panel"><strong>{formatDate(point.week_of)}</strong><div>Cost {formatCostPerTonneKm(point.cost_per_tonne_km)}</div><div>Own {formatCostPerTonneKm(point.own_history_baseline)} · {formatPercent(point.vs_own_history_pct)}</div><div>Peer {formatCostPerTonneKm(point.peer_baseline)} · {formatPercent(point.vs_similar_routes_pct)}</div>{point.verdict && <div>Verdict: {point.verdict}</div>}</div>
}
