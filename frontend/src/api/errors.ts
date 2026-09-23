import type { ErrorEnvelope } from './contracts'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown>,
    public readonly requestId: string | null,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

export const parseApiError = async (response: Response): Promise<ApiError> => {
  const requestId = response.headers.get('X-Request-ID')
  try {
    const payload = (await response.json()) as ErrorEnvelope
    if (payload.error?.code && payload.error.message) {
      return new ApiError(
        response.status,
        payload.error.code,
        payload.error.message,
        payload.error.details ?? {},
        payload.error.request_id ?? requestId,
      )
    }
  } catch {
    // Non-JSON failures intentionally use the safe fallback below.
  }
  return new ApiError(
    response.status,
    'http_error',
    'The service returned an unexpected response.',
    {},
    requestId,
  )
}

export const isNotReady = (error: unknown): boolean =>
  error instanceof ApiError && error.code === 'analysis_not_ready'
