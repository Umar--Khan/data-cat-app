import { MutationObserver, QueryObserver, type QueryObserverResult } from '@tanstack/react-query'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { ApiError, unwrap } from '@/lib/api/api-error'
import { apiClient } from '@/lib/api/client'
import { apiUrl } from '@/test/msw/handlers'
import { deleteFails, listFails } from '@/test/msw/scenarios'
import { apiRequests, worker } from '@/test/msw/worker'
import { createTestQueryClient } from '@/test/render'
import { createQueryClient } from './query-client'

const network = new ApiError({ kind: 'network', status: null, message: 'Offline' })

function httpError(status: number) {
  return new ApiError({ kind: 'http', status, message: 'Failed' })
}

describe('createQueryClient', () => {
  it('returns a fresh client each time', () => {
    expect(createQueryClient()).not.toBe(createQueryClient())
  })

  it('keeps queries fresh for 30 s and runs them whatever the online flag says', () => {
    const { queries } = createQueryClient().getDefaultOptions()

    expect(queries).toMatchObject({ staleTime: 30_000, networkMode: 'always' })
  })

  it('never retries a mutation and runs it whatever the online flag says', () => {
    const { mutations } = createQueryClient().getDefaultOptions()

    expect(mutations).toEqual({ retry: false, networkMode: 'always' })
  })

  describe('query retry', () => {
    const { retry } = createQueryClient().getDefaultOptions().queries ?? {}
    const shouldRetry = (failureCount: number, error: Error) =>
      typeof retry === 'function' && retry(failureCount, error)

    it.each([
      ['a network failure', network],
      ['a 500', httpError(500)],
      ['a 503', httpError(503)],
    ])('retries %s at most twice', (_, error) => {
      expect([0, 1, 2].map((failureCount) => shouldRetry(failureCount, error))).toEqual([
        true,
        true,
        false,
      ])
    })

    it.each([
      ['a 400', httpError(400)],
      ['a 404', httpError(404)],
      ['an error that is not an ApiError', new Error('Unexpected')],
    ])('does not retry %s', (_, error) => {
      expect(shouldRetry(0, error)).toBe(false)
    })

    it('sends a failing 5xx query three times in all, then reports the error', async () => {
      listFails()
      const observer = new QueryObserver(createTestQueryClient(), {
        queryKey: ['datasets', 'list'],
        queryFn: () => unwrap(apiClient.GET('/datasets')),
      })
      const settled = new Promise<QueryObserverResult>((resolve) => {
        observer.subscribe((result) => {
          if (result.isError) resolve(result)
        })
      })

      await expect(settled).resolves.toMatchObject({ error: { status: 500 }, failureCount: 3 })
      expect(apiRequests()).toEqual(['GET /datasets', 'GET /datasets', 'GET /datasets'])
    })

    it('sends a failing 4xx query once', async () => {
      worker.use(http.get(apiUrl('/datasets'), () => new HttpResponse(null, { status: 404 })))

      await expect(
        createTestQueryClient().query({
          queryKey: ['datasets', 'list'],
          queryFn: () => unwrap(apiClient.GET('/datasets')),
        }),
      ).rejects.toMatchObject({ status: 404 })
      expect(apiRequests()).toEqual(['GET /datasets'])
    })
  })

  it('sends a failing mutation once, even for a 5xx', async () => {
    deleteFails()
    const observer = new MutationObserver(createQueryClient(), {
      mutationFn: (id: string) =>
        unwrap(apiClient.DELETE('/datasets/{id}', { params: { path: { id } } })),
    })

    await expect(observer.mutate('1')).rejects.toMatchObject({ status: 500 })
    expect(apiRequests()).toEqual(['DELETE /datasets/1'])
  })
})
