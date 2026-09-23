import { ApiError } from '../api/errors'
import { QueryClient } from '@tanstack/react-query'

export const createQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 60_000,
        refetchOnWindowFocus: false,
        retry: (count, error) =>
          count < 1 && (!(error instanceof ApiError) || error.status >= 500),
      },
      mutations: { retry: false },
    },
  })
