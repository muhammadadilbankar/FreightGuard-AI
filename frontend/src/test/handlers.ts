import { http, HttpResponse } from 'msw'
import { anomalyDetail, anomalyList, evaluation, healthReady, metrics, rootCause, runResponse, summary, timeline } from './fixtures'

const api = 'http://127.0.0.1:8000'
export const handlers = [
  http.get(`${api}/health`, () => HttpResponse.json(healthReady)),
  http.get(`${api}/api/analysis/summary`, () => HttpResponse.json(summary)),
  http.get(`${api}/api/anomalies`, () => HttpResponse.json(anomalyList)),
  http.get(`${api}/api/anomalies/:route/:week/root-cause`, () => HttpResponse.json(rootCause)),
  http.get(`${api}/api/anomalies/:route/:week`, () => HttpResponse.json(anomalyDetail)),
  http.get(`${api}/api/routes/:route/timeline`, () => HttpResponse.json(timeline)),
  http.get(`${api}/api/evaluation/report`, () => HttpResponse.json(evaluation)),
  http.get(`${api}/api/run-metrics`, () => HttpResponse.json(metrics)),
  http.post(`${api}/api/analysis/run`, () => HttpResponse.json(runResponse)),
  http.get(`${api}/api/analysis/export.csv`, () => new HttpResponse('route,week_of\nTest-Route,2024-01-08\n', { headers: { 'Content-Type': 'text/csv', 'Content-Disposition': 'attachment; filename="freightguard-test.csv"' } })),
]
