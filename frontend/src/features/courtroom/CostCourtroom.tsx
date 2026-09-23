import { Calculator, CheckCircle2, Clipboard, FileWarning, Gavel, XCircle } from 'lucide-react'
import { useState } from 'react'
import type { AnomalyEnvelope, RootCauseEnvelope } from '../../api/contracts'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Drawer } from '../../components/ui/Drawer'
import { ErrorState } from '../../components/ui/ErrorState'
import { LoadingSkeleton } from '../../components/ui/LoadingSkeleton'
import { formatCostPerTonneKm, formatDate, formatPercent, sentenceCase } from '../../lib/format'
import { OperationalLeads } from '../root-cause/OperationalLeads'

interface Props {
  open: boolean; data?: AnomalyEnvelope; error: unknown; loading: boolean
  rootCause?: RootCauseEnvelope; rootCauseError?: unknown; rootCauseLoading?: boolean
  snapshotId?: string; onClose: () => void; onRetry: () => void; onRootCauseRetry?: () => void
}

export function CostCourtroom({ open, data, error, loading, rootCause, rootCauseError, rootCauseLoading = false, snapshotId, onClose, onRetry, onRootCauseRetry = () => undefined }: Props) {
  const [copied, setCopied] = useState(false)
  const anomaly = data?.data
  const copyReference = async () => {
    if (!anomaly || !snapshotId) return
    await navigator.clipboard.writeText(`${anomaly.route} | ${anomaly.week_of} | ${snapshotId}`)
    setCopied(true)
  }
  return <Drawer open={open} onOpenChange={(next) => { if (!next) onClose() }} title="Cost Courtroom" description="Charge, evidence, and verdict from the active trusted snapshot">
    {loading ? <LoadingSkeleton label="Loading Cost Courtroom" /> : error ? <ErrorState error={error} onRetry={onRetry} /> : anomaly ? <>
      <Card className="court-section"><h3><Calculator aria-hidden="true" /> CHARGE</h3><p><strong>{anomaly.route}</strong> · week of {formatDate(anomaly.week_of)}</p><div className="charge-grid"><Charge label="Observed cost" value={`${formatCostPerTonneKm(anomaly.cost_per_tonne_km)} / tonne-km`} /><Charge label="Own-history baseline" value={formatCostPerTonneKm(anomaly.own_history_baseline)} /><Charge label="Own deviation" value={`${formatPercent(anomaly.vs_own_history_pct)} · ${anomaly.own_threshold_breached ? 'Triggered' : 'Did not trigger'}`} /><Charge label="Peer baseline" value={formatCostPerTonneKm(anomaly.peer_baseline)} /><Charge label="Peer deviation" value={`${formatPercent(anomaly.vs_similar_routes_pct)} · ${anomaly.peer_threshold_breached ? 'Triggered' : 'Did not trigger'}`} /><Charge label="Audit sample" value={`${anomaly.history_weeks_used} history weeks · ${anomaly.peer_routes_used} peers`} /></div></Card>
      <Card className="court-section"><h3><FileWarning aria-hidden="true" /> EVIDENCE</h3>{anomaly.evidence.length === 0 ? <p>No retrieved evidence was available for this candidate.</p> : <ul className="evidence-list">{anomaly.evidence.map((evidence) => <li className="evidence-item" key={evidence.note_id}><div className="section-heading"><strong>{evidence.note_id}</strong><Badge tone={evidence.role === 'rejected' ? 'danger' : evidence.evidence_level}>{sentenceCase(evidence.role)}</Badge></div><p>{evidence.original_text}</p><div className="facts"><span>Scope <strong>{sentenceCase(evidence.scope_type)}</strong></span><span>Effective <strong>{formatDate(evidence.effective_from)} – {formatDate(evidence.effective_to)}</strong></span><span>Event <strong>{sentenceCase(evidence.event_type)}</strong></span><span>Impact <strong>{sentenceCase(evidence.impact_direction)}</strong></span>{evidence.magnitude_text && <span>Magnitude <strong>{evidence.magnitude_text}</strong></span>}</div><h4>Validation gates</h4><ul className="gate-list">{evidence.gate_results.map((gate) => <li className="gate-row" key={gate.gate}>{gate.status === 'pass' ? <CheckCircle2 color="var(--color-justified)" aria-label="Pass" /> : <XCircle color="var(--color-unexplained)" aria-label="Fail" />}<div><strong>{sentenceCase(gate.gate)}</strong> · {sentenceCase(gate.status)}<br /><small>{gate.reason}{gate.reason_code ? ` Code: ${gate.reason_code}.` : ''}</small></div></li>)}</ul>{evidence.rejection_codes.length > 0 && <p><strong>Rejection reasons:</strong> {evidence.rejection_codes.map(sentenceCase).join(', ')}</p>}</li>)}</ul>}</Card>
      {anomaly.verdict === 'unexplained' && anomaly.operational_root_cause_available && <Card className="court-section"><OperationalLeads data={rootCause} error={rootCauseError} loading={rootCauseLoading} onRetry={onRootCauseRetry} /></Card>}
      <Card className="court-section"><h3><Gavel aria-hidden="true" /> VERDICT</h3><Badge tone={anomaly.verdict}>{sentenceCase(anomaly.verdict)}</Badge><p>{anomaly.reason}</p><div className="facts"><span>Flagged <strong>{anomaly.flagged}</strong></span><span>Decision code <strong>{sentenceCase(anomaly.decision_code)}</strong></span><span>Matched note <strong>{anomaly.matched_note_id ?? 'None'}</strong></span><span>Supporting citations <strong>{anomaly.supporting_note_ids.join(', ') || 'None'}</strong></span><span>Wording source <strong>{sentenceCase(anomaly.explanation_source)}</strong></span><span>Fallback <strong>{anomaly.fallback_used ? 'Used' : 'Not used'}</strong></span></div><p><small>Unexplained means the supplied context did not justify this anomaly; it does not imply fraud or wrongdoing.</small></p></Card>
      <Button variant="secondary" onClick={() => void copyReference()}><Clipboard size={16} /> Copy audit reference</Button>
      <span className="sr-only" role="status" aria-live="polite">{copied ? 'Audit reference copied.' : ''}</span>
    </> : null}
  </Drawer>
}

function Charge({ label, value }: { label: string; value: string }) {
  return <div className="charge-item"><span>{label}</span><strong>{value}</strong></div>
}
