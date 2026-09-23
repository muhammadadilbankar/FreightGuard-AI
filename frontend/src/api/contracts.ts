import type { components } from './generated'

type Schemas = components['schemas']

export type Health = Schemas['HealthResponse']
export type SummaryEnvelope = Schemas['DataEnvelope_AnalysisSummaryData_']
export type Summary = Schemas['AnalysisSummaryData']
export type Anomaly = Schemas['AnomalyData']
export type AnomalyEnvelope = Schemas['DataEnvelope_AnomalyData_']
export type AnomalyListEnvelope = Schemas['DataEnvelope_AnomalyListData_']
export type TimelineEnvelope = Schemas['DataEnvelope_RouteTimelineData_']
export type TimelinePoint = Schemas['TimelinePointData']
export type EvaluationEnvelope = Schemas['DataEnvelope_EvaluationReportData_']
export type MetricsEnvelope = Schemas['DataEnvelope_RunMetricsData_']
export type RunEnvelope = Schemas['DataEnvelope_RunAnalysisData_']
export type RunRequest = Schemas['RunAnalysisRequest']
export type ErrorEnvelope = Schemas['ErrorResponse']
export type ResponseMeta = Schemas['ResponseMeta']
export type RootCauseEnvelope = Schemas['DataEnvelope_RootCauseData_']
export type RootCause = Schemas['RootCauseData']
export type DecompositionLens = Schemas['DecompositionLensData']
export type CategoryContribution = Schemas['CategoryContributionData']

export type Verdict = 'justified' | 'partially_explained' | 'unexplained'
export type Trigger = 'own_history' | 'peer' | 'both'
export type SortField =
  | 'week_of'
  | 'route'
  | 'route_type'
  | 'cost_per_tonne_km'
  | 'vs_own_history_pct'
  | 'vs_similar_routes_pct'
  | 'verdict'

export interface AnomalyFilters {
  route?: string
  routeType?: string
  verdict?: Verdict
  trigger?: Trigger
  weekFrom?: string
  weekTo?: string
  minOwnDeviationPct?: string
  minPeerDeviationPct?: string
  sortBy: SortField
  sortOrder: 'asc' | 'desc'
  page: number
  limit: number
}
