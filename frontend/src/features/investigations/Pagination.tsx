import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { ResponseMeta } from '../../api/contracts'
import { Button } from '../../components/ui/Button'

export function Pagination({ meta, page, onPage }: { meta: ResponseMeta; page: number; onPage: (page: number) => void }) {
  const pagination = meta.pagination
  if (!pagination) return null
  return <nav className="pagination" aria-label="Investigation pages"><Button variant="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}><ChevronLeft size={16} /> Previous</Button><span>Page {page} · {pagination.total} results</span><Button variant="secondary" disabled={!pagination.has_more} onClick={() => onPage(page + 1)}>Next <ChevronRight size={16} /></Button></nav>
}
