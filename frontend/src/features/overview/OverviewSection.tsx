import type { Summary, Verdict } from '../../api/contracts'
import { Card } from '../../components/ui/Card'
import { formatDateRange, formatInteger } from '../../lib/format'

const cards = (summary: Summary) => [
  ['Shipments analysed', summary.shipment_count, ''],
  ['Route-week records', summary.weekly_record_count, ''],
  ['Anomaly candidates', summary.candidate_count, ''],
  ['Require attention', summary.unexplained_count, 'danger'],
] as const

export function OverviewSection({ summary, onVerdict }: { summary: Summary; onVerdict: (verdict?: Verdict) => void }) {
  const total = Math.max(summary.candidate_count, 1)
  const verdicts: Array<[Verdict, string, number]> = [
    ['justified', 'Justified', summary.justified_count],
    ['partially_explained', 'Partially explained', summary.partially_explained_count],
    ['unexplained', 'Unexplained', summary.unexplained_count],
  ]
  return (
    <section className="section" aria-labelledby="overview-heading">
      <div className="section-heading"><div><p className="eyebrow">Trusted overview</p><h2 id="overview-heading">The freight network at a glance</h2></div></div>
      <div className="stats-grid">
        {cards(summary).map(([label, value, tone]) => <Card className={`stat-card ${tone ? `stat-card--${tone}` : ''}`} key={label}><span className="stat-label">{label}</span><strong className="stat-value">{formatInteger(value)}</strong></Card>)}
      </div>
      <div className="overview-grid">
        <Card className="panel">
          <div className="section-heading"><div><h3>Verdict distribution</h3><p>Canonical Evidence Gate outcomes</p></div><ButtonLike onClick={() => onVerdict()}>Show all {summary.candidate_count}</ButtonLike></div>
          <div className="verdict-bars" aria-hidden="true">{verdicts.map(([value, , count]) => <button type="button" tabIndex={-1} key={value} className={`verdict-bar verdict-bar--${value}`} style={{ width: `${(count / total) * 100}%` }} onClick={() => onVerdict(value)} />)}</div>
          <div className="verdict-legend">{verdicts.map(([value, label, count]) => <button className="legend-button" type="button" key={value} onClick={() => onVerdict(value)} aria-label={`Show ${count} ${label.toLowerCase()} anomalies`}><span className={`badge badge--${value}`}>{label}</span><strong className="stat-value">{count}</strong></button>)}</div>
        </Card>
        <Card className="panel">
          <h3>Analysis coverage</h3>
          <div className="facts">
            <span><strong>{summary.route_count}</strong> routes</span>
            <span><strong>{summary.route_type_count}</strong> route types</span>
            <span><strong>{formatDateRange(summary.analysis_from, summary.analysis_to)}</strong></span>
            <span>Threshold <strong>{summary.anomaly_threshold_percent}%</strong></span>
            <span>Mode <strong>{summary.explanation_mode}</strong></span>
            <span>Evaluation <strong>{summary.evaluation_status}</strong></span>
          </div>
        </Card>
      </div>
    </section>
  )
}

function ButtonLike({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return <button type="button" className="button button--ghost" onClick={onClick}>{children}</button>
}
