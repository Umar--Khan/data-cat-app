import { QueryClient } from '@tanstack/react-query'
import { ApiError } from '@/lib/api/api-error'

const maxRetries = 2

// A failure with no status to judge by (no response, or an unreadable one) or a 5xx can pass; any
// other error would fail the same way again.
function isTransient(error: Error): boolean {
  return error instanceof ApiError && (error.status === null || error.status >= 500)
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: (failureCount, error) => failureCount < maxRetries && isTransient(error),
        // The browser's online flag says nothing about whether a localhost API is reachable.
        networkMode: 'always',
      },
      mutations: {
        // POST is not idempotent: every attempt would run curation again.
        retry: false,
        networkMode: 'always',
      },
    },
  })
}
