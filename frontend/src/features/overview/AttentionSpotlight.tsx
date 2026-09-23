import { ArrowRight, ScanSearch } from 'lucide-react'
import type { Anomaly } from '../../api/contracts'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { formatDate, formatPercent } from '../../lib/format'

export function AttentionSpotlight({ anomaly, onInvestigate }: { anomaly?: Anomaly; onInvestigate: (anomaly: Anomaly) => void }) {
  if (!anomaly) return <EmptyState title="No anomaly needs the spotlight" message="This snapshot has no matching unexplained or partially explained candidate." />
  return (
    <Card className="panel spotlight">
      <p className="eyebrow"><ScanSearch size={15} aria-hidden="true" /> Largest {anomaly.verdict === 'unexplained' ? 'unexplained' : 'partially explained'} own-history deviation</p>
      <h3>{anomaly.route}</h3><p>{formatDate(anomaly.week_of)} · {anomaly.route_type}</p>
      <div className="spotlight-metric">{formatPercent(anomaly.vs_own_history_pct)}</div>
      <p>{anomaly.reason}</p>
      <Button onClick={() => onInvestigate(anomaly)}>Investigate <ArrowRight size={17} /></Button>
    </Card>
  )
}
