import type { AnomalyFilters } from '../../api/contracts'
import { Button } from '../../components/ui/Button'
import { useState } from 'react'

export function InvestigationFilters({ filters, onApply, onClear }: { filters: AnomalyFilters; onApply: (patch: Partial<AnomalyFilters>) => void; onClear: () => void }) {
  const [draft, setDraft] = useState(filters)
  const field = (key: keyof AnomalyFilters) => (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setDraft({ ...draft, [key]: event.target.value || undefined })
  const dateError = Boolean(draft.weekFrom && draft.weekTo && draft.weekFrom > draft.weekTo)
  return (
    <form className="card filters" onSubmit={(event) => event.preventDefault()} aria-label="Investigation filters">
      <div className="field"><label htmlFor="route-filter">Route</label><input id="route-filter" value={draft.route ?? ''} onChange={field('route')} maxLength={120} placeholder="Exact route" /></div>
      <div className="field"><label htmlFor="type-filter">Route type</label><input id="type-filter" value={draft.routeType ?? ''} onChange={field('routeType')} maxLength={80} placeholder="Exact type" /></div>
      <div className="field"><label htmlFor="verdict-filter">Verdict</label><select id="verdict-filter" value={draft.verdict ?? ''} onChange={field('verdict')}><option value="">All verdicts</option><option value="unexplained">Unexplained</option><option value="partially_explained">Partially explained</option><option value="justified">Justified</option></select></div>
      <div className="field"><label htmlFor="trigger-filter">Trigger</label><select id="trigger-filter" value={draft.trigger ?? ''} onChange={field('trigger')}><option value="">All triggers</option><option value="both">Both</option><option value="own_history">Own history</option><option value="peer">Peer</option></select></div>
      <div className="field"><label htmlFor="week-from">Week from</label><input id="week-from" type="date" value={draft.weekFrom ?? ''} onChange={field('weekFrom')} aria-invalid={dateError} /></div>
      <div className="field"><label htmlFor="week-to">Week to</label><input id="week-to" type="date" value={draft.weekTo ?? ''} onChange={field('weekTo')} aria-invalid={dateError} />{dateError && <small role="alert">Week from must be before week to.</small>}</div>
      <div className="field"><label htmlFor="own-min">Min own deviation (%)</label><input id="own-min" inputMode="decimal" value={draft.minOwnDeviationPct ?? ''} onChange={field('minOwnDeviationPct')} /></div>
      <div className="field"><label htmlFor="peer-min">Min peer deviation (%)</label><input id="peer-min" inputMode="decimal" value={draft.minPeerDeviationPct ?? ''} onChange={field('minPeerDeviationPct')} /></div>
      <div className="field"><label htmlFor="sort-field">Sort by</label><select id="sort-field" value={draft.sortBy} onChange={field('sortBy')}><option value="vs_own_history_pct">Own deviation</option><option value="vs_similar_routes_pct">Peer deviation</option><option value="week_of">Week</option><option value="route">Route</option><option value="cost_per_tonne_km">Cost</option><option value="verdict">Verdict</option></select></div>
      <div className="field"><label htmlFor="sort-order">Direction</label><select id="sort-order" value={draft.sortOrder} onChange={field('sortOrder')}><option value="desc">Descending</option><option value="asc">Ascending</option></select></div>
      <div className="filter-actions"><Button type="button" disabled={dateError} onClick={() => onApply(draft)}>Apply filters</Button><Button variant="secondary" type="button" onClick={onClear}>Clear</Button></div>
    </form>
  )
}
