import { config } from '../config'
import { parseApiError } from './errors'

export interface BlobResult {
  blob: Blob
  filename: string
  etag: string | null
  requestId: string | null
}

const urlFor = (path: string, params?: URLSearchParams): string => {
  if (!path.startsWith('/')) throw new Error('API paths must be absolute')
  const url = new URL(`${config.apiBaseUrl}${path}`)
  if (params) url.search = params.toString()
  return url.toString()
}

const request = async <T>(
  path: string,
  init: RequestInit = {},
  params?: URLSearchParams,
): Promise<T> => {
  const response = await fetch(urlFor(path, params), {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  })
  if (!response.ok) throw await parseApiError(response)
  return (await response.json()) as T
}

const safeFilename = (header: string | null): string => {
  const match = header?.match(/filename="?([^";]+)"?/i)
  const candidate = match?.[1]?.replace(/[^a-zA-Z0-9._-]/g, '_')
  return candidate && candidate.toLowerCase().endsWith('.csv')
    ? candidate
    : 'freightguard-analysis.csv'
}

export const apiClient = {
  get: <T>(path: string, params?: URLSearchParams, signal?: AbortSignal) =>
    request<T>(path, { signal }, params),
  post: <T>(path: string, body: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body), signal }),
  blob: async (path: string, signal?: AbortSignal): Promise<BlobResult> => {
    const response = await fetch(urlFor(path), { signal })
    if (!response.ok) throw await parseApiError(response)
    return {
      blob: await response.blob(),
      filename: safeFilename(response.headers.get('Content-Disposition')),
      etag: response.headers.get('ETag'),
      requestId: response.headers.get('X-Request-ID'),
    }
  },
}

export { safeFilename }
