import type { Anomaly, AnomalyFilters, AnomalyListEnvelope } from '../../api/contracts'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { LoadingSkeleton } from '../../components/ui/LoadingSkeleton'
import { InvestigationCards } from './InvestigationCards'
import { InvestigationFilters } from './InvestigationFilters'
import { InvestigationTable } from './InvestigationTable'
import { Pagination } from './Pagination'

export function InvestigationSection({ data, error, loading, filters, selectedKey, onFilters, onClear, onSelect, onRetry }: { data?: AnomalyListEnvelope; error: unknown; loading: boolean; filters: AnomalyFilters; selectedKey?: string; onFilters: (patch: Partial<AnomalyFilters>) => void; onClear: () => void; onSelect: (item: Anomaly) => void; onRetry: () => void }) {
  const items = data?.data.items ?? []
  return <section className="section" aria-labelledby="investigation-heading"><div className="section-heading"><div><p className="eyebrow">Investigation queue</p><h2 id="investigation-heading">Trace every candidate to its evidence</h2><p aria-live="polite">{data?.meta.pagination?.total ?? 'Loading'} matching candidates</p></div></div><InvestigationFilters key={JSON.stringify(filters)} filters={filters} onApply={onFilters} onClear={onClear} />{loading && !data ? <LoadingSkeleton label="Loading investigation queue" /> : error ? <ErrorState error={error} onRetry={onRetry} /> : items.length === 0 ? <EmptyState title="No candidates match these filters" message="Clear or adjust the filters to inspect other candidates in this snapshot." /> : <div className="card"><InvestigationTable anomalies={items} selectedKey={selectedKey} onSelect={onSelect} /><InvestigationCards anomalies={items} onSelect={onSelect} /><Pagination meta={data!.meta} page={filters.page} onPage={(page) => onFilters({ page })} /></div>}</section>
}
