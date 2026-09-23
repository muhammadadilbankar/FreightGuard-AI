import { apiClient } from '../client'
import type {
  AnomalyEnvelope,
  AnomalyFilters,
  AnomalyListEnvelope,
  EvaluationEnvelope,
  Health,
  MetricsEnvelope,
  RunEnvelope,
  RunRequest,
  RootCauseEnvelope,
  SummaryEnvelope,
  TimelineEnvelope,
  AssistantRequest,
  AssistantResponse,
} from '../contracts'

const set = (params: URLSearchParams, key: string, value: string | number | undefined) => {
  if (value !== undefined && value !== '') params.set(key, String(value))
}

export const anomalyParams = (filters: AnomalyFilters): URLSearchParams => {
  const params = new URLSearchParams()
  set(params, 'route', filters.route)
  set(params, 'route_type', filters.routeType)
  set(params, 'verdict', filters.verdict)
  set(params, 'trigger', filters.trigger)
  set(params, 'week_from', filters.weekFrom)
  set(params, 'week_to', filters.weekTo)
  set(params, 'min_own_deviation_pct', filters.minOwnDeviationPct)
  set(params, 'min_peer_deviation_pct', filters.minPeerDeviationPct)
  set(params, 'sort_by', filters.sortBy)
  set(params, 'sort_order', filters.sortOrder)
  set(params, 'limit', filters.limit)
  set(params, 'offset', (filters.page - 1) * filters.limit)
  return params
}

export const endpoints = {
  health: (signal?: AbortSignal) => apiClient.get<Health>('/health', undefined, signal),
  summary: (signal?: AbortSignal) =>
    apiClient.get<SummaryEnvelope>('/api/analysis/summary', undefined, signal),
  anomalies: (filters: AnomalyFilters, signal?: AbortSignal) =>
    apiClient.get<AnomalyListEnvelope>('/api/anomalies', anomalyParams(filters), signal),
  spotlight: (verdict: string, signal?: AbortSignal) => {
    const params = new URLSearchParams({
      verdict,
      sort_by: 'vs_own_history_pct',
      sort_order: 'desc',
      limit: '1',
      offset: '0',
    })
    return apiClient.get<AnomalyListEnvelope>('/api/anomalies', params, signal)
  },
  anomaly: (route: string, week: string, signal?: AbortSignal) =>
    apiClient.get<AnomalyEnvelope>(
      `/api/anomalies/${encodeURIComponent(route)}/${encodeURIComponent(week)}`,
      undefined,
      signal,
    ),
  rootCause: (route: string, week: string, signal?: AbortSignal) =>
    apiClient.get<RootCauseEnvelope>(
      `/api/anomalies/${encodeURIComponent(route)}/${encodeURIComponent(week)}/root-cause`,
      undefined,
      signal,
    ),
  timeline: (route: string, from?: string, to?: string, signal?: AbortSignal) => {
    const params = new URLSearchParams()
    set(params, 'week_from', from)
    set(params, 'week_to', to)
    return apiClient.get<TimelineEnvelope>(
      `/api/routes/${encodeURIComponent(route)}/timeline`,
      params,
      signal,
    )
  },
  evaluation: (includeChecks: boolean, signal?: AbortSignal) =>
    apiClient.get<EvaluationEnvelope>(
      '/api/evaluation/report',
      new URLSearchParams({ include_checks: String(includeChecks) }),
      signal,
    ),
  metrics: (signal?: AbortSignal) =>
    apiClient.get<MetricsEnvelope>('/api/run-metrics', undefined, signal),
  run: (body: RunRequest, signal?: AbortSignal) =>
    apiClient.post<RunEnvelope>('/api/analysis/run', body, signal),
  assistant: (body: AssistantRequest, signal?: AbortSignal) =>
    apiClient.post<AssistantResponse>('/api/assistant/query', body, signal),
  exportCsv: (signal?: AbortSignal) => apiClient.blob('/api/analysis/export.csv', signal),
}
