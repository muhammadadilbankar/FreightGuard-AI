import { Search } from 'lucide-react'
import type { Anomaly } from '../../api/contracts'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { formatCostPerTonneKm, formatDate, formatPercent, sentenceCase } from '../../lib/format'

export function InvestigationTable({ anomalies, selectedKey, onSelect }: { anomalies: Anomaly[]; selectedKey?: string; onSelect: (anomaly: Anomaly) => void }) {
  return (
    <div className="table-wrap">
      <table><caption>{anomalies.length} candidates on this page. Values are supplied by the active backend snapshot.</caption><thead><tr><th scope="col">Route</th><th scope="col">Week</th><th scope="col" className="numeric">Cost / tonne-km</th><th scope="col" className="numeric">Own deviation</th><th scope="col" className="numeric">Peer deviation</th><th scope="col">Trigger</th><th scope="col">Verdict</th><th scope="col">Evidence</th><th scope="col"><span className="sr-only">Action</span></th></tr></thead>
        <tbody>{anomalies.map((item) => <tr key={item.candidate_key} data-selected={selectedKey === item.candidate_key}><td><strong>{item.route}</strong><br /><small>{item.route_type}</small></td><td>{formatDate(item.week_of)}</td><td className="numeric">{formatCostPerTonneKm(item.cost_per_tonne_km)}</td><td className="numeric">{formatPercent(item.vs_own_history_pct)}</td><td className="numeric">{formatPercent(item.vs_similar_routes_pct)}</td><td><Badge>{sentenceCase(item.trigger)}</Badge></td><td><Badge tone={item.verdict}>{sentenceCase(item.verdict)}</Badge></td><td>{item.matched_note_id ?? (item.supporting_note_ids.length ? `${item.supporting_note_ids.length} supporting` : 'No accepted note')}</td><td><Button variant="ghost" onClick={() => onSelect(item)} aria-label={`Investigate ${item.route} for week ${item.week_of}`}><Search size={16} /> Investigate</Button></td></tr>)}</tbody>
      </table>
    </div>
  )
}
