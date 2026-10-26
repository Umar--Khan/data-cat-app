import { describe, expect, it } from 'vitest'
import { apiUrl } from './handlers'
import {
  createCurationFailed,
  createInvalid,
  deleteFails,
  deleteNotFound,
  hold,
  listFails,
} from './scenarios'
import { seedDatasets, store } from './store'
import { apiRequests } from './worker'

const tradeConfirmations = {
  name: 'Trade Confirmations',
  owner: 'Middle Office',
  description: 'Daily export of confirmed trades.',
}

function post(body: unknown = tradeConfirmations) {
  return fetch(apiUrl('/datasets'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

function remove(id: string) {
  return fetch(apiUrl(`/datasets/${id}`), { method: 'DELETE' })
}

function storedIds() {
  return store.list().map(({ id }) => id)
}

describe('mock API scenarios', () => {
  it('listFails answers 500 problems until stopped', async () => {
    const stop = listFails()

    const failed = await fetch(apiUrl('/datasets'))
    expect(failed.status).toBe(500)
    expect(failed.headers.get('Content-Type')).toBe('application/problem+json')
    expect(await failed.json()).toMatchObject({ detail: 'The server hit an unexpected error.' })
    expect((await fetch(apiUrl('/datasets'))).status).toBe(500)

    stop()
    expect(await (await fetch(apiUrl('/datasets'))).json()).toEqual(seedDatasets)
  })

  it('createInvalid answers with the given field errors and stores nothing', async () => {
    const fieldErrors = [{ field: 'owner', message: 'This field must not be blank.' }]
    createInvalid(fieldErrors)

    const response = await post()

    expect(response.status).toBe(400)
    expect(await response.json()).toMatchObject({
      type: '/problems/validation-error',
      detail: 'The request body has an invalid field: owner.',
      errors: fieldErrors,
    })
    expect(storedIds()).toEqual(['1', '2', '3'])
  })

  it('createCurationFailed stores the record without curation and answers 201', async () => {
    createCurationFailed()

    const response = await post()

    expect(response.status).toBe(201)
    expect(await response.json()).toMatchObject({
      id: '4',
      tags: [],
      summary: null,
      curation: {
        status: 'failed',
        provider: 'anthropic',
        detail: 'The AI service could not be reached.',
      },
    })
    expect(storedIds()).toEqual(['1', '2', '3', '4'])
  })

  it('deleteFails fails every delete and deletes nothing', async () => {
    deleteFails()

    expect((await remove('1')).status).toBe(500)
    expect((await remove('2')).status).toBe(500)
    expect(storedIds()).toEqual(['1', '2', '3'])
  })

  it('deleteFails with an id fails only that delete', async () => {
    deleteFails('2')

    expect((await remove('1')).status).toBe(200)
    expect((await remove('2')).status).toBe(500)
    expect(storedIds()).toEqual(['2', '3'])
  })

  it.each([
    ['any id', undefined],
    ['that id', '1'],
  ])('deleteNotFound for %s removes the record first and answers 404', async (_, id) => {
    deleteNotFound(id)

    const response = await remove('1')

    expect(response.status).toBe(404)
    expect(await response.json()).toMatchObject({ title: 'Dataset not found' })
    expect(storedIds()).toEqual(['2', '3'])
  })

  it('deleteNotFound with an id leaves other deletes alone', async () => {
    deleteNotFound('1')

    expect((await remove('2')).status).toBe(200)
    expect(storedIds()).toEqual(['1', '3'])
  })

  describe('hold', () => {
    it('holds a request until the test releases it', async () => {
      const gate = hold('GET')
      let settled = false
      const response = fetch(apiUrl('/datasets')).then((result) => {
        settled = true
        return result
      })

      const request = await gate.arrived
      expect(new URL(request.url).pathname).toBe('/datasets')
      expect(settled).toBe(false)
      expect(apiRequests()).toEqual(['GET /datasets'])

      gate.release()
      expect((await response).status).toBe(200)
    })

    it('holds only its method, and only one request per gate', async () => {
      const gate = hold('DELETE')

      expect((await fetch(apiUrl('/datasets'))).status).toBe(200)
      const held = remove('1')
      await gate.arrived
      expect((await remove('2')).status).toBe(200)

      gate.release()
      expect((await held).status).toBe(200)
    })

    it('gives overlapping requests their gates in the order hold was called', async () => {
      const first = hold('DELETE')
      const second = hold('DELETE')

      const firstResponse = remove('1')
      expect(new URL((await first.arrived).url).pathname).toBe('/datasets/1')
      const secondResponse = remove('2')
      expect(new URL((await second.arrived).url).pathname).toBe('/datasets/2')

      second.release()
      expect((await secondResponse).status).toBe(200)
      expect(storedIds()).toEqual(['1', '3'])
      first.release()
      expect((await firstResponse).status).toBe(200)
    })

    it('delays a scenario set up after it, which then answers', async () => {
      const gate = hold('DELETE')
      deleteFails()

      const response = remove('1')
      await gate.arrived
      gate.release()

      expect((await response).status).toBe(500)
    })
  })
})
