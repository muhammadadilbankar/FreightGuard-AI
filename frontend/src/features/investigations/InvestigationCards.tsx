import type { Anomaly } from '../../api/contracts'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { formatCostPerTonneKm, formatDate, formatPercent, sentenceCase } from '../../lib/format'

export function InvestigationCards({ anomalies, onSelect }: { anomalies: Anomaly[]; onSelect: (anomaly: Anomaly) => void }) {
  return <div className="mobile-cards">{anomalies.map((item) => <Card className="anomaly-card" key={item.candidate_key}><div className="section-heading"><div><strong>{item.route}</strong><p>{formatDate(item.week_of)}</p></div><Badge tone={item.verdict}>{sentenceCase(item.verdict)}</Badge></div><div className="facts"><span>Cost <strong>{formatCostPerTonneKm(item.cost_per_tonne_km)}</strong></span><span>Own <strong>{formatPercent(item.vs_own_history_pct)}</strong></span><span>Peer <strong>{formatPercent(item.vs_similar_routes_pct)}</strong></span><span>Trigger <strong>{sentenceCase(item.trigger)}</strong></span></div><Button variant="secondary" onClick={() => onSelect(item)}>Investigate anomaly</Button></Card>)}</div>
}
