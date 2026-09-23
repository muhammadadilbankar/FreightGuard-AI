import type { AnomalyFilters } from './contracts'

export const queryKeys = {
  health: ['health'] as const,
  summary: ['analysis', 'summary'] as const,
  anomalies: (filters: AnomalyFilters) => ['anomalies', filters] as const,
  spotlight: ['anomalies', 'spotlight'] as const,
  anomaly: (route: string, week: string) => ['anomaly', route, week] as const,
  rootCause: (route: string, week: string) => ['root-cause', route, week] as const,
  timeline: (route: string, from?: string, to?: string) =>
    ['timeline', route, from ?? '', to ?? ''] as const,
  evaluation: (includeChecks: boolean) => ['evaluation', includeChecks] as const,
  metrics: ['run-metrics'] as const,
  snapshotRoots: [
    ['analysis'],
    ['anomalies'],
    ['anomaly'],
    ['root-cause'],
    ['timeline'],
    ['evaluation'],
    ['run-metrics'],
  ] as const,
}
