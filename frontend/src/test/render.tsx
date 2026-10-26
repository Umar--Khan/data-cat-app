import { QueryClientProvider, type QueryClient } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { render, renderHook } from 'vitest-browser-react'
import { Toaster } from '@/app/providers'
import { createQueryClient } from '@/app/query-client'

/**
 * The app's query client with the same retry policy, minus the backoff between attempts, so a
 * test of a failing request sees every retry without waiting seconds for them.
 */
export function createTestQueryClient(): QueryClient {
  const queryClient = createQueryClient()
  const defaults = queryClient.getDefaultOptions()
  queryClient.setDefaultOptions({ ...defaults, queries: { ...defaults.queries, retryDelay: 0 } })
  return queryClient
}

function providers(queryClient: QueryClient) {
  return function Providers({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
        <Toaster />
      </QueryClientProvider>
    )
  }
}

interface ProviderOptions {
  queryClient?: QueryClient
}

/** Renders inside a fresh query client and a toaster; the client is returned for cache checks. */
export async function renderWithProviders(
  ui: ReactNode,
  { queryClient = createTestQueryClient() }: ProviderOptions = {},
) {
  const screen = await render(ui, { wrapper: providers(queryClient) })
  return Object.assign(screen, { queryClient })
}

/** renderHook inside a fresh query client and a toaster; the client is returned for cache checks. */
export async function renderHookWithProviders<Result>(
  hook: () => Result,
  { queryClient = createTestQueryClient() }: ProviderOptions = {},
) {
  const view = await renderHook(hook, { wrapper: providers(queryClient) })
  return Object.assign(view, { queryClient })
}
