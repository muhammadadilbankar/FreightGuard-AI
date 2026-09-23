import { ArrowRight, Bot, Send } from 'lucide-react'
import { FormEvent, useState } from 'react'
import type { AssistantContext, AssistantResponse } from '../../api/contracts'
import { useAssistant } from '../../api/hooks'
import { Drawer } from '../../components/ui/Drawer'
import { Button } from '../../components/ui/Button'
import { ApiError } from '../../api/errors'

const STARTERS = [
  'Show unexplained anomalies',
  'Which anomaly had the largest peer deviation?',
  'How many anomalies are in this snapshot?',
  'Show run metrics',
]

export function InvestigationAssistant({ open, onOpenChange, snapshotId }: { open: boolean; onOpenChange: (open: boolean) => void; snapshotId?: string }) {
  const assistant = useAssistant()
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<AssistantResponse>()
  const [context, setContext] = useState<AssistantContext>()

  const activeContext = context?.snapshot_id === snapshotId ? context : undefined
  const activeAnswer = answer?.meta.snapshot_id === snapshotId ? answer : undefined

  const ask = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed || assistant.isPending) return
    assistant.mutate(
      { question: trimmed, context: activeContext },
      {
        onSuccess: (result) => {
          setAnswer(result)
          setContext(result.data.context)
          setQuestion('')
        },
      },
    )
  }
  const submit = (event: FormEvent) => { event.preventDefault(); ask(question) }
  const navigate = (target?: string | null) => {
    if (!target) return
    const url = new URL(target, window.location.origin)
    window.history.pushState({}, '', `${url.pathname}${url.search}`)
    window.dispatchEvent(new PopStateEvent('popstate'))
    onOpenChange(false)
  }

  return <Drawer open={open} onOpenChange={onOpenChange} title="Investigation Assistant" description="Read-only answers from the active validated snapshot" closeLabel="Close investigation assistant">
    <div className="assistant-boundary"><Bot size={18} aria-hidden="true" /><span>Facts, verdicts, note matches, and calculations come from stored backend records. The assistant cannot change them.</span></div>
    {!activeAnswer && <div className="assistant-starters"><h3>Try a supported question</h3>{STARTERS.map((starter) => <button type="button" key={starter} onClick={() => ask(starter)}>{starter}<ArrowRight size={15} /></button>)}</div>}
    {activeAnswer && <AssistantAnswer answer={activeAnswer} onAsk={ask} onNavigate={navigate} />}
    {assistant.error && <div className="assistant-error" role="alert"><strong>Unable to answer.</strong><span>{assistant.error instanceof ApiError ? assistant.error.message : 'The assistant request failed.'}</span></div>}
    <form className="assistant-form" onSubmit={submit}>
      <label htmlFor="assistant-question">Ask about anomalies, evidence, trends, operational leads, or run diagnostics</label>
      <div><input id="assistant-question" value={question} maxLength={800} onChange={(event) => setQuestion(event.target.value)} placeholder="Why was this route-week flagged?" disabled={assistant.isPending} /><Button type="submit" disabled={!question.trim() || assistant.isPending}><Send size={16} />{assistant.isPending ? 'Checking…' : 'Ask'}</Button></div>
    </form>
  </Drawer>
}

function AssistantAnswer({ answer, onAsk, onNavigate }: { answer: AssistantResponse; onAsk: (value: string) => void; onNavigate: (target?: string | null) => void }) {
  const citations = new Map(answer.data.citations.map((citation) => [citation.citation_id, citation]))
  return <section className="assistant-answer" aria-live="polite">
    <div className="assistant-answer__meta"><span>{answer.meta.planner_mode} planner</span><span>{answer.meta.tool_count} read-only tool{answer.meta.tool_count === 1 ? '' : 's'}</span><span>Snapshot {answer.meta.snapshot_id.slice(0, 8)}</span></div>
    <h3>{answer.data.title}</h3>
    {answer.data.claims.map((claim) => <p key={claim.claim_id}>{claim.text} <span className="assistant-citations">{claim.citation_ids.map((id) => { const citation = citations.get(id); return <button type="button" key={id} onClick={() => onNavigate(citation?.navigation_target)} disabled={!citation?.navigation_target} title={citation?.label}>[{citation?.label ?? id}]</button> })}</span></p>)}
    {answer.data.table && <div className="table-wrap assistant-table"><table><caption>{answer.data.table.caption}</caption><thead><tr>{answer.data.table.columns.map((column) => <th key={column.key}>{column.label}</th>)}</tr></thead><tbody>{answer.data.table.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, columnIndex) => { const isCitation = columnIndex === answer.data.table?.citation_column_index; const citation = isCitation && typeof cell === 'string' ? citations.get(cell) : undefined; return <td key={columnIndex}>{isCitation ? <button type="button" onClick={() => onNavigate(citation?.navigation_target)} disabled={!citation?.navigation_target}>{citation?.label ?? 'Source'}</button> : displayCell(cell)}</td> })}</tr>)}</tbody></table></div>}
    {answer.data.clarification && <div className="assistant-clarification"><strong>{answer.data.clarification.question}</strong>{answer.data.clarification.options.map((option) => <button type="button" key={option.option_id} onClick={() => onAsk(option.value)}>{option.label}</button>)}</div>}
    {answer.data.limitations.length > 0 && <ul className="assistant-limitations">{answer.data.limitations.map((item) => <li key={item}>{item}</li>)}</ul>}
    {answer.data.actions.map((action) => <Button type="button" variant="secondary" key={`${action.action}-${action.label}`} onClick={() => { const route = action.params.route; const week = action.params.week_of; if (route) onNavigate(`/?selectedRoute=${encodeURIComponent(route)}${week ? `&selectedWeek=${encodeURIComponent(week)}` : ''}`) }}>{action.label}</Button>)}
  </section>
}

function displayCell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return 'Unsupported value'
}
