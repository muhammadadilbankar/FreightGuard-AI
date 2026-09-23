import { useRef, useState, type KeyboardEvent } from 'react'
import type { DecompositionLens, RootCauseEnvelope } from '../../api/contracts'
import { Badge } from '../../components/ui/Badge'
import { ErrorState } from '../../components/ui/ErrorState'
import { LoadingSkeleton } from '../../components/ui/LoadingSkeleton'
import { formatCostPerTonneKm, formatPercent, sentenceCase } from '../../lib/format'

export function OperationalLeads({ data, error, loading, onRetry }: { data?: RootCauseEnvelope; error: unknown; loading: boolean; onRetry: () => void }) {
  const [active, setActive] = useState<'transporter' | 'material'>('transporter')
  const tabs = useRef<Array<HTMLButtonElement | null>>([])
  if (loading) return <LoadingSkeleton label="Loading operational leads" />
  if (error) return <ErrorState title="Operational leads unavailable" error={error} onRetry={onRetry} />
  if (!data) return null
  const result = data.data
  const lens = result[active]
  const keyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
    event.preventDefault()
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + 2) % 2
    const value = next === 0 ? 'transporter' : 'material'
    setActive(value)
    tabs.current[next]?.focus()
  }
  const primaryMetrics = new Set(['shipment_count', 'average_load_tonnes', 'weighted_average_distance_km'])
  return <section aria-labelledby="operational-leads-title">
    <div className="root-boundary" role="note">Operational leads are derived from shipment patterns. They are not validated context evidence and do not change the unexplained verdict.</div>
    <div className="section-heading"><div><h4 id="operational-leads-title">Operational Leads</h4><p>{result.reference_week_count} prior route weeks · <Badge tone="neutral">{sentenceCase(result.support_level)} support</Badge></p></div><strong>{formatCostPerTonneKm(result.target_gap)} gap</strong></div>
    <div className="root-metrics">{result.operational_metrics.filter((item) => primaryMetrics.has(item.metric)).map((item) => <Metric key={item.metric} item={item} />)}</div>
    <details><summary>Additional operational metrics</summary><div className="root-metrics">{result.operational_metrics.filter((item) => !primaryMetrics.has(item.metric)).map((item) => <Metric key={item.metric} item={item} />)}</div></details>
    <div className="root-tabs" role="tablist" aria-label="Operational decomposition lens">{(['transporter', 'material'] as const).map((value, index) => <button key={value} ref={(node) => { tabs.current[index] = node }} type="button" role="tab" id={`tab-${value}`} aria-selected={active === value} aria-controls={`panel-${value}`} tabIndex={active === value ? 0 : -1} onClick={() => setActive(value)} onKeyDown={(event) => keyDown(event, index)}>{sentenceCase(value)} lens</button>)}</div>
    <div role="tabpanel" id={`panel-${active}`} aria-labelledby={`tab-${active}`}><Lens lens={lens} /></div>
    <ul className="root-caveats">{result.caveats.map((item) => <li key={item}>{item}</li>)}</ul>
  </section>
}

function Metric({ item }: { item: RootCauseEnvelope['data']['operational_metrics'][number] }) {
  return <div className="root-metric"><span>{sentenceCase(item.metric)}</span><strong>{item.current_value.toFixed(2)} {item.unit}</strong><small>Reference {item.reference_mean.toFixed(2)} · change {item.absolute_change >= 0 ? '+' : ''}{item.absolute_change.toFixed(2)}{item.percentage_change == null ? '' : ` (${formatPercent(item.percentage_change)})`}</small><small>{item.interpretation}</small></div>
}

function Lens({ lens }: { lens: DecompositionLens }) {
  const maximum = Math.max(...lens.contributions.map((item) => Math.abs(item.net_contribution)), 1e-12)
  return <div className="root-lens"><p>This lens independently partitions the full own-history gap; do not add it to the other lens.</p><p><strong>Reconstruction:</strong> {formatCostPerTonneKm(lens.reconstructed_gap)} = {formatCostPerTonneKm(lens.target_gap)} (error {lens.reconstruction_error.toExponential(2)})</p>
    <div className="contribution-chart" role="img" aria-label={`${sentenceCase(lens.lens)} contribution chart. Positive values increase the gap and negative values offset it.`}>{lens.contributions.map((item) => <div className="contribution-row" key={item.category}><span>{item.category}</span><div className="contribution-track"><i className={item.net_contribution >= 0 ? 'positive' : 'negative'} style={{ width: `${Math.abs(item.net_contribution) / maximum * 50}%` }} /></div><strong>{item.net_contribution >= 0 ? '+' : ''}{item.net_contribution.toFixed(4)}</strong></div>)}</div>
    <div className="table-wrap"><table><caption>Accessible {lens.lens} contribution details</caption><thead><tr><th>Category</th><th>Direction</th><th className="numeric">Mix</th><th className="numeric">Rate</th><th className="numeric">Entry / exit</th><th className="numeric">Net INR/t-km</th><th>Support</th></tr></thead><tbody>{lens.contributions.map((item) => <tr key={item.category}><td><details><summary>{item.category}</summary><small>Current share {formatPercent(item.current_tonne_km_share == null ? null : item.current_tonne_km_share * 100)}; reference share {formatPercent(item.reference_mean_tonne_km_share == null ? null : item.reference_mean_tonne_km_share * 100)}. Current rate {formatCostPerTonneKm(item.current_cost_per_tonne_km)}; reference rate {formatCostPerTonneKm(item.reference_mean_cost_per_tonne_km)}. {item.current_shipment_count} current and {item.reference_shipment_count} reference shipments across {item.reference_weeks_present} weeks. {item.caveats.join(' ')}</small></details></td><td>{item.net_contribution >= 0 ? 'Positive contributor' : 'Offset'}</td><td className="numeric">{item.mix_effect.toFixed(4)}</td><td className="numeric">{item.rate_effect.toFixed(4)}</td><td className="numeric">{item.entry_effect !== 0 ? `Entry ${item.entry_effect.toFixed(4)}` : item.exit_effect !== 0 ? `Exit ${item.exit_effect.toFixed(4)}` : '—'}</td><td className="numeric">{item.net_contribution.toFixed(4)}</td><td><Badge tone="neutral">{sentenceCase(item.support_level)}</Badge></td></tr>)}</tbody></table></div>
  </div>
}
