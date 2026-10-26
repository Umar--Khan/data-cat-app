import { describe, expect, expectTypeOf, it } from 'vitest'
import type { ProblemDetails } from '@/lib/api/schema.gen'
import { apiRequests } from '@/test/msw/worker'
import { apiClient } from './client'

describe('apiClient', () => {
  it('sends requests to the configured API base URL', async () => {
    const { response } = await apiClient.GET('/datasets')

    expect(response.url).toBe('http://api.test/datasets')
    expect(apiRequests()).toEqual(['GET /datasets'])
  })

  // application/problem+json does not end in /json, which openapi-fetch's JSON-only media type
  // would miss; the client keeps the default media type so these bodies stay typed.
  it('parses and types an application/problem+json error body', async () => {
    const { data, error, response } = await apiClient.DELETE('/datasets/{id}', {
      params: { path: { id: '9' } },
    })

    expectTypeOf(error).toEqualTypeOf<ProblemDetails | undefined>()
    expect(response.headers.get('Content-Type')).toBe('application/problem+json')
    expect(data).toBeUndefined()
    expect(error).toEqual({
      type: '/problems/dataset-not-found',
      title: 'Dataset not found',
      status: 404,
      detail: 'No dataset has id "9". It may have been deleted already.',
      instance: '/datasets/9',
      errors: [],
    })
  })
})
