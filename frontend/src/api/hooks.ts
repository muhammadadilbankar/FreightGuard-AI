import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'
import { endpoints } from './endpoints'
import type { AnomalyFilters, RunRequest } from './contracts'
import { queryKeys } from './queryKeys'

export const useHealth = () =>
  useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => endpoints.health(signal),
    staleTime: 5_000,
    refetchInterval: (query) => {
      const data = query.state.data
      return !data?.ready || data.run_state === 'running' ? 2_000 : false
    },
  })

export const useSummary = (enabled = true) =>
  useQuery({
    queryKey: queryKeys.summary,
    queryFn: ({ signal }) => endpoints.summary(signal),
    enabled,
  })

export const useAnomalies = (filters: AnomalyFilters, enabled = true) =>
  useQuery({
    queryKey: queryKeys.anomalies(filters),
    queryFn: ({ signal }) => endpoints.anomalies(filters, signal),
    enabled,
    placeholderData: keepPreviousData,
  })

export const useSpotlight = (verdict: string, enabled = true) =>
  useQuery({
    queryKey: [...queryKeys.spotlight, verdict],
    queryFn: ({ signal }) => endpoints.spotlight(verdict, signal),
    enabled,
  })

export const useAnomaly = (route?: string, week?: string, enabled = true) =>
  useQuery({
    queryKey: queryKeys.anomaly(route ?? '', week ?? ''),
    queryFn: ({ signal }) => endpoints.anomaly(route!, week!, signal),
    enabled: enabled && Boolean(route && week),
  })

export const useRootCause = (route?: string, week?: string, enabled = true) =>
  useQuery({
    queryKey: queryKeys.rootCause(route ?? '', week ?? ''),
    queryFn: ({ signal }) => endpoints.rootCause(route!, week!, signal),
    enabled: enabled && Boolean(route && week),
  })

export const useTimeline = (route?: string, from?: string, to?: string, enabled = true) =>
  useQuery({
    queryKey: queryKeys.timeline(route ?? '', from, to),
    queryFn: ({ signal }) => endpoints.timeline(route!, from, to, signal),
    enabled: enabled && Boolean(route),
  })

export const useEvaluation = (includeChecks: boolean, enabled = true) =>
  useQuery({
    queryKey: queryKeys.evaluation(includeChecks),
    queryFn: ({ signal }) => endpoints.evaluation(includeChecks, signal),
    enabled,
  })

export const useMetrics = (enabled = true) =>
  useQuery({
    queryKey: queryKeys.metrics,
    queryFn: ({ signal }) => endpoints.metrics(signal),
    enabled,
  })

export const useRunAnalysis = () =>
  useMutation({ mutationFn: (request: RunRequest) => endpoints.run(request) })
