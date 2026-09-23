import { useEffect, useState } from 'react'
import type { AnomalyFilters } from '../../api/contracts'
import {
  parseInvestigationState,
  serializeInvestigationState,
  type InvestigationState,
} from '../../lib/urlState'

export function useInvestigationParams() {
  const [state, setState] = useState(() => parseInvestigationState(window.location.search))
  useEffect(() => {
    const onPopState = () => setState(parseInvestigationState(window.location.search))
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  const update = (next: InvestigationState, replace = false) => {
    const url = `${window.location.pathname}${serializeInvestigationState(next)}`
    window.history[replace ? 'replaceState' : 'pushState']({}, '', url)
    setState(next)
  }
  const setFilters = (patch: Partial<AnomalyFilters>) =>
    update({ ...state, filters: { ...state.filters, ...patch, page: patch.page ?? 1 } })
  const select = (route?: string, week?: string) =>
    update({ ...state, selectedRoute: route, selectedWeek: week })
  return { state, setFilters, select, update }
}
