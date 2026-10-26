import { describe, expect, expectTypeOf, it } from 'vitest'
import { ApiError } from '@/lib/api/api-error'
import type { Dataset } from '@/lib/api/schema.gen'
import { seedDatasets, store } from '@/test/msw/store'
import { apiRequests } from '@/test/msw/worker'
import { datasetsApi } from './datasets-api'

const tradeConfirmations = {
  name: 'Trade Confirmations',
  owner: 'Middle Office',
  description:
    'Daily export of confirmed trades including instrument type, counterparty, notional value, and settlement date.',
}

describe('datasetsApi', () => {
  it('lists the datasets', async () => {
    expectTypeOf(datasetsApi.list).returns.resolves.toEqualTypeOf<Dataset[]>()
    await expect(datasetsApi.list()).resolves.toEqual(seedDatasets)
    expect(apiRequests()).toEqual(['GET /datasets'])
  })

  it('passes the signal on, so a cancelled list request is abandoned', async () => {
    const controller = new AbortController()
    controller.abort()

    await expect(datasetsApi.list(controller.signal)).rejects.toBe(controller.signal.reason)
  })

  it('creates a dataset and resolves to the stored record', async () => {
    expectTypeOf(datasetsApi.create).returns.resolves.toEqualTypeOf<Dataset>()
    const created = await datasetsApi.create({
      ...tradeConfirmations,
      name: '  Trade Confirmations ',
    })

    expect(created).toMatchObject({
      id: '4',
      ...tradeConfirmations,
      curation: { status: 'completed', provider: 'keyword', detail: null },
    })
    expect(store.list().at(-1)).toEqual(created)
    expect(apiRequests()).toEqual(['POST /datasets'])
  })

  it('deletes a dataset by id and resolves to the deleted record', async () => {
    expectTypeOf(datasetsApi.delete).returns.resolves.toEqualTypeOf<Dataset>()
    await expect(datasetsApi.delete('2')).resolves.toEqual(seedDatasets[1])
    expect(store.list().map(({ id }) => id)).toEqual(['1', '3'])
    expect(apiRequests()).toEqual(['DELETE /datasets/2'])
  })

  it('rejects with an ApiError when the API answers with a problem', async () => {
    const request = datasetsApi.delete('9')

    await expect(request).rejects.toThrow(ApiError)
    await expect(request).rejects.toMatchObject({ kind: 'http', status: 404 })
  })
})
