import { describe, expect, it, onTestFinished, vi } from 'vitest'
import { apiUrl } from './handlers'
import { seedDatasets, store } from './store'

const tradeConfirmations = {
  name: 'Trade Confirmations',
  owner: 'Middle Office',
  description: 'Daily export of confirmed trades.',
}

function post(body: unknown) {
  return fetch(apiUrl('/datasets'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: typeof body === 'string' ? body : JSON.stringify(body),
  })
}

async function problemOf(response: Response) {
  const body: unknown = await response.json()
  return { contentType: response.headers.get('Content-Type'), body }
}

function problem(fields: Record<string, unknown>) {
  return {
    contentType: 'application/problem+json',
    body: { instance: '/datasets', errors: [], ...fields },
  }
}

describe('mock API handlers', () => {
  it('lists the three seed records in order', async () => {
    const response = await fetch(apiUrl('/datasets'))

    expect(response.status).toBe(200)
    expect(await response.json()).toEqual(seedDatasets)
  })

  it('starts from whatever records a test resets the store to', async () => {
    store.reset([])

    expect(await (await fetch(apiUrl('/datasets'))).json()).toEqual([])
  })

  it('creates a trimmed, curated record with a 201 and a relative Location', async () => {
    const response = await post({ ...tradeConfirmations, name: '  Trade Confirmations  ' })
    const created: unknown = await response.json()

    expect(response.status).toBe(201)
    expect(response.headers.get('Location')).toBe('/datasets/4')
    expect(created).toEqual({
      id: '4',
      ...tradeConfirmations,
      tags: ['catalogue'],
      summary: 'A dataset named Trade Confirmations.',
      curation: { status: 'completed', provider: 'keyword', detail: null },
      createdAt: store.list().at(-1)?.createdAt,
    })
    expect(store.list().at(-1)?.createdAt).toMatch(/Z$/)
  })

  it('never reuses an id', async () => {
    await post(tradeConfirmations)
    await fetch(apiUrl('/datasets/4'), { method: 'DELETE' })

    expect(await (await post(tradeConfirmations)).json()).toMatchObject({ id: '5' })
  })

  it('names every missing field', async () => {
    expect(await problemOf(await post({}))).toEqual(
      problem({
        type: '/problems/validation-error',
        title: 'Invalid request body',
        status: 400,
        detail: 'The request body has invalid fields: name, owner, description.',
        errors: ['name', 'owner', 'description'].map((field) => ({
          field,
          message: 'This field is required.',
        })),
      }),
    )
  })

  it.each([
    ['blank after trimming', { name: '   ' }, 'This field must not be blank.'],
    ['not a string', { name: 42 }, 'This field must be a string.'],
    [
      'over 120 code points',
      { name: '𝔸'.repeat(121) },
      'This field must be at most 120 characters.',
    ],
  ])('rejects a name that is %s', async (_, override, message) => {
    expect(await problemOf(await post({ ...tradeConfirmations, ...override }))).toEqual(
      problem({
        type: '/problems/validation-error',
        title: 'Invalid request body',
        status: 400,
        detail: 'The request body has an invalid field: name.',
        errors: [{ field: 'name', message }],
      }),
    )
  })

  it('accepts 120 code points, counted as the API counts them', async () => {
    const response = await post({ ...tradeConfirmations, name: '𝔸'.repeat(120) })

    expect(response.status).toBe(201)
  })

  it('rejects fields the API does not accept', async () => {
    expect(await problemOf(await post({ ...tradeConfirmations, tags: ['finance'] }))).toEqual(
      problem({
        type: '/problems/validation-error',
        title: 'Invalid request body',
        status: 400,
        detail: 'The request body has an invalid field: tags.',
        errors: [{ field: 'tags', message: 'This field is not allowed.' }],
      }),
    )
  })

  it.each([
    ['invalid JSON', '{'],
    ['an array', []],
    ['null', null],
  ])('rejects a body that is %s as malformed', async (_, body) => {
    expect(await problemOf(await post(body))).toEqual(
      problem({
        type: '/problems/malformed-body',
        title: 'Malformed request body',
        status: 400,
        detail: 'The request body must be a JSON object sent as application/json.',
      }),
    )
    expect(store.list()).toEqual(seedDatasets)
  })

  it('deletes a record and answers with it', async () => {
    const response = await fetch(apiUrl('/datasets/1'), { method: 'DELETE' })

    expect(response.status).toBe(200)
    expect(await response.json()).toEqual(seedDatasets[0])
    expect(store.list().map(({ id }) => id)).toEqual(['2', '3'])
  })

  it('answers a delete of an unknown id with a 404 problem', async () => {
    const response = await fetch(apiUrl('/datasets/9'), { method: 'DELETE' })

    expect(await problemOf(response)).toEqual(
      problem({
        type: '/problems/dataset-not-found',
        title: 'Dataset not found',
        status: 404,
        detail: 'No dataset has id "9". It may have been deleted already.',
        instance: '/datasets/9',
      }),
    )
  })

  it('fails a request no handler matches at once, naming it, without reaching the network', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    onTestFinished(() => {
      consoleError.mockRestore()
    })

    const response = await fetch(apiUrl('/health'))

    expect(response.status).toBe(500)
    expect(consoleError).toHaveBeenCalledWith(expect.stringContaining('GET http://api.test/health'))
  })
})
