import type { AnomalyFilters, SortField, Trigger, Verdict } from '../api/contracts'

const verdicts = new Set<Verdict>(['justified', 'partially_explained', 'unexplained'])
const triggers = new Set<Trigger>(['own_history', 'peer', 'both'])
const sorts = new Set<SortField>([
  'week_of',
  'route',
  'route_type',
  'cost_per_tonne_km',
  'vs_own_history_pct',
  'vs_similar_routes_pct',
  'verdict',
])
const bounded = (value: string | null, max = 120) =>
  value && value.length <= max ? value : undefined

export interface InvestigationState {
  filters: AnomalyFilters
  selectedRoute?: string
  selectedWeek?: string
}

export const parseInvestigationState = (search: string): InvestigationState => {
  const params = new URLSearchParams(search)
  const verdictValue = params.get('verdict') as Verdict | null
  const triggerValue = params.get('trigger') as Trigger | null
  const sortValue = params.get('sortBy') as SortField | null
  const page = Number.parseInt(params.get('page') ?? '1', 10)
  return {
    filters: {
      route: bounded(params.get('route')),
      routeType: bounded(params.get('routeType')),
      verdict: verdictValue && verdicts.has(verdictValue) ? verdictValue : undefined,
      trigger: triggerValue && triggers.has(triggerValue) ? triggerValue : undefined,
      weekFrom: bounded(params.get('weekFrom'), 10),
      weekTo: bounded(params.get('weekTo'), 10),
      minOwnDeviationPct: bounded(params.get('minOwnDeviationPct'), 20),
      minPeerDeviationPct: bounded(params.get('minPeerDeviationPct'), 20),
      sortBy: sortValue && sorts.has(sortValue) ? sortValue : 'vs_own_history_pct',
      sortOrder: params.get('sortOrder') === 'asc' ? 'asc' : 'desc',
      page: Number.isFinite(page) && page > 0 ? Math.min(page, 10_000) : 1,
      limit: 20,
    },
    selectedRoute: bounded(params.get('selectedRoute')),
    selectedWeek: bounded(params.get('selectedWeek'), 10),
  }
}

export const serializeInvestigationState = (state: InvestigationState): string => {
  const params = new URLSearchParams()
  const { filters } = state
  const entries: Array<[string, string | number | undefined]> = [
    ['route', filters.route],
    ['routeType', filters.routeType],
    ['verdict', filters.verdict],
    ['trigger', filters.trigger],
    ['weekFrom', filters.weekFrom],
    ['weekTo', filters.weekTo],
    ['minOwnDeviationPct', filters.minOwnDeviationPct],
    ['minPeerDeviationPct', filters.minPeerDeviationPct],
    ['sortBy', filters.sortBy],
    ['sortOrder', filters.sortOrder],
    ['page', filters.page > 1 ? filters.page : undefined],
    ['selectedRoute', state.selectedRoute],
    ['selectedWeek', state.selectedWeek],
  ]
  entries.forEach(([key, value]) => {
    if (value !== undefined && value !== '') params.set(key, String(value))
  })
  const value = params.toString()
  return value ? `?${value}` : ''
}
