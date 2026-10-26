import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { apiClient } from '@/lib/api/client'
import type { ProblemDetails } from '@/lib/api/schema.gen'
import { apiUrl } from '@/test/msw/handlers'
import { createInvalid } from '@/test/msw/scenarios'
import { seedDatasets } from '@/test/msw/store'
import { worker } from '@/test/msw/worker'
import { ApiError, networkErrorMessage, unwrap } from './api-error'

const notFound: ProblemDetails = {
  type: '/problems/dataset-not-found',
  title: 'Dataset not found',
  status: 404,
  detail: 'No dataset has id "9". It may have been deleted already.',
  instance: '/datasets/9',
  errors: [],
}

function problemResponse(body: unknown, contentType = 'application/problem+json') {
  return new Response(JSON.stringify(body), {
    status: 404,
    headers: { 'Content-Type': contentType },
  })
}

function listWith(response: () => Response) {
  worker.use(http.get(apiUrl('/datasets'), response))
  return unwrap(apiClient.GET('/datasets'))
}

describe('ApiError', () => {
  it('is an Error with its kind, status, message, field errors and cause', () => {
    const cause = new TypeError('Failed to fetch')
    const error = new ApiError({ kind: 'network', status: null, message: 'Offline', cause })

    expect(error).toBeInstanceOf(Error)
    expect(error).toMatchObject({
      name: 'ApiError',
      kind: 'network',
      status: null,
      message: 'Offline',
      fieldErrors: [],
      cause,
    })
  })

  describe('fromResponse', () => {
    it("takes a problem's detail as the message, and its field errors", () => {
      const errors = [{ field: 'name', message: 'This field must not be blank.' }]
      const error = ApiError.fromResponse(problemResponse({}), { ...notFound, errors })

      expect(error).toMatchObject({
        kind: 'http',
        status: 404,
        message: 'No dataset has id "9". It may have been deleted already.',
        fieldErrors: errors,
      })
    })

    it("falls back to the problem's title when its detail is empty", () => {
      const error = ApiError.fromResponse(problemResponse({}), { ...notFound, detail: '' })

      expect(error.message).toBe('Dataset not found')
    })

    it('recognises the problem media type with parameters and in any case', () => {
      const response = problemResponse({}, 'Application/Problem+JSON; charset=utf-8')

      expect(ApiError.fromResponse(response, notFound).message).toBe(notFound.detail)
    })

    it.each([
      ['a JSON error that is not a problem', 'application/json', notFound],
      ['a problem body that is not an object', 'application/problem+json', 'Not Found'],
      ['a problem body missing its detail', 'application/problem+json', { title: 'Not Found' }],
      [
        'a problem whose errors are not field errors',
        'application/problem+json',
        { ...notFound, errors: [null] },
      ],
      ['no body at all', 'application/problem+json', undefined],
    ])('reports the status alone for %s', (_, contentType, body) => {
      const error = ApiError.fromResponse(problemResponse(body, contentType), body)

      expect(error).toMatchObject({
        kind: 'http',
        status: 404,
        message: 'The server returned an unexpected error (HTTP 404).',
        fieldErrors: [],
      })
    })
  })
})

describe('unwrap', () => {
  it('resolves to the data of a successful response', async () => {
    await expect(unwrap(apiClient.GET('/datasets'))).resolves.toEqual(seedDatasets)
  })

  it('throws the problem openapi-fetch parsed from an application/problem+json body', async () => {
    const fieldErrors = [{ field: 'owner', message: 'This field is required.' }]
    createInvalid(fieldErrors)

    const request = unwrap(
      apiClient.POST('/datasets', { body: { name: 'Sales', owner: '', description: 'Daily.' } }),
    )

    await expect(request).rejects.toThrow(ApiError)
    await expect(request).rejects.toMatchObject({
      kind: 'http',
      status: 400,
      message: 'The request body has an invalid field: owner.',
      fieldErrors,
    })
  })

  it('throws an HTTP error with the status for a body that is not a problem', async () => {
    const request = listWith(
      () =>
        new HttpResponse('<h1>Bad gateway</h1>', {
          status: 502,
          headers: { 'Content-Type': 'text/html' },
        }),
    )

    await expect(request).rejects.toMatchObject({
      kind: 'http',
      status: 502,
      message: 'The server returned an unexpected error (HTTP 502).',
    })
  })

  it('throws an HTTP error for an empty error response', async () => {
    const request = listWith(() => new HttpResponse(null, { status: 503 }))

    await expect(request).rejects.toMatchObject({ kind: 'http', status: 503 })
  })

  it('throws a network error with the user-facing message when no response arrives', async () => {
    const request = listWith(() => HttpResponse.error())

    const error: unknown = await request.catch((reason: unknown) => reason)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      kind: 'network',
      status: null,
      message: networkErrorMessage,
      fieldErrors: [],
    })
    expect((error as ApiError).cause).toBeInstanceOf(TypeError)
    expect(networkErrorMessage).toBe(
      'Could not reach the server. Check your connection and try again.',
    )
  })

  it('passes an abort through untouched', async () => {
    const controller = new AbortController()
    controller.abort()

    await expect(unwrap(apiClient.GET('/datasets', { signal: controller.signal }))).rejects.toBe(
      controller.signal.reason,
    )
  })

  it('passes any other failure through untouched', async () => {
    const request = listWith(() =>
      HttpResponse.text('not json', { headers: { 'Content-Type': 'application/json' } }),
    )

    await expect(request).rejects.toThrow(SyntaxError)
  })
})
