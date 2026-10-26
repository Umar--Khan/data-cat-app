import { http, HttpResponse } from 'msw'
import { toast } from 'sonner'
import { describe, expect, it, onTestFinished } from 'vitest'
import { datasetKeys } from '@/features/datasets/api/query-keys'
import { ApiError } from '@/lib/api/api-error'
import type { Dataset } from '@/lib/api/schema.gen'
import { apiUrl } from '@/test/msw/handlers'
import {
  createCurationFailed,
  createInvalid,
  deleteFails,
  deleteNotFound,
  hold,
  listFails,
} from '@/test/msw/scenarios'
import { keywordCurated, seedDatasets, store } from '@/test/msw/store'
import { apiRequests, worker } from '@/test/msw/worker'
import { renderHookWithProviders } from '@/test/render'
import { useCreateDataset, useDatasets, useDeleteDataset } from './use-datasets'

const [customerTransactions, productInventory] = seedDatasets as [Dataset, Dataset, Dataset]

const tradeConfirmations = {
  name: 'Trade Confirmations',
  owner: 'Middle Office',
  description:
    'Daily export of confirmed trades including instrument type, counterparty, notional value, and settlement date.',
}

function ids(datasets: Dataset[] | undefined) {
  return datasets?.map(({ id }) => id)
}

/**
 * Holds the next GET /datasets and, once released, answers it with the catalogue as it is now: a
 * refresh that started before a write and would undo it if it landed. Later GETs read the store.
 */
function holdStaleRefresh() {
  const before = store.list()
  let arrive: () => void = () => undefined
  let release: () => void = () => undefined
  const arrived = new Promise<void>((resolve) => (arrive = resolve))
  const released = new Promise<void>((resolve) => (release = resolve))
  // A test that fails before releasing it would otherwise leave the mock API waiting forever.
  onTestFinished(release)
  worker.use(
    http.get(
      apiUrl('/datasets'),
      async () => {
        arrive()
        await released
        return HttpResponse.json(before)
      },
      { once: true },
    ),
  )
  return { arrived, release }
}

/** The list as the hook returns it, every render recorded, plus both mutations. */
async function renderCatalogue() {
  const rendered: (string[] | undefined)[] = []
  const view = await renderHookWithProviders(() => {
    const list = useDatasets()
    rendered.push(ids(list.data))
    return { list, create: useCreateDataset(), remove: useDeleteDataset() }
  })
  await expect.poll(() => view.result.current.list.isSuccess).toBe(true)
  return Object.assign(view, {
    rendered,
    shownIds: () => ids(view.result.current.list.data),
    cachedIds: () => ids(view.queryClient.getQueryData<Dataset[]>(datasetKeys.list)),
    /** Asserts that no render from now on shows this row. */
    neverShowsAgain(id: string) {
      const from = rendered.length
      return () => rendered.slice(from).every((shown) => !shown?.includes(id))
    },
  })
}

describe('useDatasets', () => {
  it('loads the list into the list query', async () => {
    const view = await renderCatalogue()

    expect(view.result.current.list.data).toEqual(seedDatasets)
    expect(view.queryClient.getQueryData(['datasets', 'list'])).toEqual(seedDatasets)
    expect(apiRequests()).toEqual(['GET /datasets'])
  })

  it('is pending with no data until the first load arrives', async () => {
    const gate = hold('GET')
    const view = await renderHookWithProviders(() => useDatasets())
    await gate.arrived

    expect(view.result.current).toMatchObject({ isPending: true, data: undefined })

    gate.release()
    await expect.poll(() => view.result.current.data).toEqual(seedDatasets)
  })

  it('reports a failed first load after retrying it twice', async () => {
    listFails()
    const view = await renderHookWithProviders(() => useDatasets())

    await expect.poll(() => view.result.current.isLoadingError).toBe(true)
    expect(view.result.current.data).toBeUndefined()
    expect(view.result.current.error).toBeInstanceOf(ApiError)
    expect(view.result.current.error).toMatchObject({
      status: 500,
      message: 'The server hit an unexpected error.',
    })
    expect(apiRequests()).toEqual(['GET /datasets', 'GET /datasets', 'GET /datasets'])
  })

  it('keeps the last list when a background refresh fails, and recovers on a retry', async () => {
    const view = await renderCatalogue()
    const stop = listFails()

    await view.act(() => view.result.current.list.refetch())

    expect(view.result.current.list).toMatchObject({ isRefetchError: true, data: seedDatasets })
    expect(view.result.current.list.error).toMatchObject({ status: 500 })

    stop()
    await view.act(() => view.result.current.list.refetch())
    expect(view.result.current.list).toMatchObject({ isSuccess: true, data: seedDatasets })
  })
})

describe('useCreateDataset', () => {
  it('appends the created record to the list without refetching it, and toasts', async () => {
    const view = await renderCatalogue()

    const created = await view.result.current.create.mutateAsync({
      ...tradeConfirmations,
      owner: ' Middle Office ',
    })

    expect(created).toMatchObject({ id: '4', ...tradeConfirmations })
    expect(view.queryClient.getQueryData(datasetKeys.list)).toEqual([...seedDatasets, created])
    await expect.poll(() => view.shownIds()).toEqual(['1', '2', '3', '4'])
    expect(apiRequests()).toEqual(['GET /datasets', 'POST /datasets'])
    expect(toast.getToasts()).toEqual([
      expect.objectContaining({
        type: 'success',
        title: 'Added "Trade Confirmations"',
        duration: 5_000,
      }),
    ])
    expect(toast.getToasts()[0]).not.toHaveProperty('closeButton')
  })

  it('warns, with the reason, when the record was saved without curation', async () => {
    createCurationFailed()
    const view = await renderCatalogue()

    const created = await view.result.current.create.mutateAsync(tradeConfirmations)

    expect(created).toMatchObject({ tags: [], summary: null, curation: { status: 'failed' } })
    expect(view.cachedIds()).toEqual(['1', '2', '3', '4'])
    expect(toast.getToasts()).toEqual([
      expect.objectContaining({
        type: 'warning',
        title: 'Saved "Trade Confirmations" without AI tags',
        description: 'The AI service could not be reached.',
        duration: 10_000,
        closeButton: true,
      }),
    ])
  })

  it('cancels a refresh in flight, so older data cannot overwrite the new record', async () => {
    const view = await renderCatalogue()
    const refresh = holdStaleRefresh()
    void view.queryClient.invalidateQueries({ queryKey: datasetKeys.list })
    await refresh.arrived

    await view.result.current.create.mutateAsync(tradeConfirmations)
    expect(view.cachedIds()).toEqual(['1', '2', '3', '4'])
    refresh.release()

    // The cancelled refresh starts again, and reads the catalogue with the new record in it.
    await expect
      .poll(() => view.queryClient.getQueryState(datasetKeys.list)?.fetchStatus)
      .toBe('idle')
    expect(view.cachedIds()).toEqual(['1', '2', '3', '4'])
    expect(apiRequests()).toEqual([
      'GET /datasets',
      'GET /datasets',
      'POST /datasets',
      'GET /datasets',
    ])
  })

  it('leaves a first load running instead of cancelling it into a list that never loads', async () => {
    const firstLoad = hold('GET')
    const view = await renderHookWithProviders(() => ({
      list: useDatasets(),
      create: useCreateDataset(),
    }))
    await firstLoad.arrived

    await view.result.current.create.mutateAsync(tradeConfirmations)

    expect(view.queryClient.getQueryState(datasetKeys.list)?.fetchStatus).toBe('fetching')
    firstLoad.release()
    await expect.poll(() => ids(view.result.current.list.data)).toEqual(['1', '2', '3', '4'])
  })

  it('adds no list to the cache when none was loaded', async () => {
    const view = await renderHookWithProviders(() => useCreateDataset())

    await view.result.current.mutateAsync(tradeConfirmations)

    expect(view.queryClient.getQueryData(datasetKeys.list)).toBeUndefined()
    expect(toast.getToasts()).toEqual([expect.objectContaining({ type: 'success' })])
  })

  it('rejects with the ApiError and toasts nothing, so the form can show it inline', async () => {
    const fieldErrors = [{ field: 'name', message: 'This field must not be blank.' }]
    createInvalid(fieldErrors)
    const view = await renderCatalogue()

    const request = view.result.current.create.mutateAsync({ ...tradeConfirmations, name: ' ' })

    await expect(request).rejects.toThrow(ApiError)
    await expect(request).rejects.toMatchObject({ status: 400, fieldErrors })
    await expect.poll(() => view.result.current.create.error).toBeInstanceOf(ApiError)
    expect(view.cachedIds()).toEqual(['1', '2', '3'])
    expect(toast.getToasts()).toEqual([])
  })

  it('is pending while the POST is in flight', async () => {
    const gate = hold('POST')
    const view = await renderCatalogue()

    const request = view.result.current.create.mutateAsync(tradeConfirmations)
    await gate.arrived

    await expect.poll(() => view.result.current.create.isPending).toBe(true)
    expect(view.queryClient.isMutating({ mutationKey: ['datasets', 'create'] })).toBe(1)
    gate.release()
    await request
    await expect.poll(() => view.result.current.create.isSuccess).toBe(true)
  })
})

describe('useDeleteDataset', () => {
  it('hides the row while the delete is pending, then removes it and toasts', async () => {
    const view = await renderCatalogue()
    const gate = hold('DELETE')
    const neverShown = view.neverShowsAgain('1')

    view.result.current.remove.mutate(customerTransactions)
    await gate.arrived

    await expect.poll(() => view.shownIds()).toEqual(['2', '3'])
    expect(view.cachedIds()).toEqual(['1', '2', '3'])
    expect(view.result.current.remove.isPending).toBe(true)

    gate.release()
    await expect.poll(() => view.result.current.remove.isSuccess).toBe(true)
    expect(view.cachedIds()).toEqual(['2', '3'])
    expect(view.shownIds()).toEqual(['2', '3'])
    expect(neverShown()).toBe(true)
    expect(toast.getToasts()).toEqual([
      expect.objectContaining({
        type: 'success',
        title: 'Deleted "Customer Transactions"',
        duration: 5_000,
      }),
    ])
  })

  it('removes the row and says so when it was already deleted elsewhere', async () => {
    deleteNotFound('1')
    const view = await renderCatalogue()
    const neverShown = view.neverShowsAgain('1')

    view.result.current.remove.mutate(customerTransactions)

    await expect.poll(() => view.result.current.remove.isSuccess).toBe(true)
    expect(view.cachedIds()).toEqual(['2', '3'])
    expect(neverShown()).toBe(true)
    expect(toast.getToasts()).toEqual([
      expect.objectContaining({
        type: 'info',
        title: '"Customer Transactions" was already removed',
        duration: 5_000,
      }),
    ])
  })

  it('brings the row back on failure, toasts the error and refreshes without waiting', async () => {
    deleteFails('1')
    const view = await renderCatalogue()
    const refresh = hold('GET')

    view.result.current.remove.mutate(customerTransactions)

    await expect.poll(() => view.result.current.remove.isError).toBe(true)
    await refresh.arrived
    expect(view.queryClient.getQueryState(datasetKeys.list)?.fetchStatus).toBe('fetching')
    expect(view.shownIds()).toEqual(['1', '2', '3'])
    expect(toast.getToasts()).toEqual([
      expect.objectContaining({
        type: 'error',
        title: 'Couldn\'t delete "Customer Transactions"',
        description: 'The server hit an unexpected error.',
        duration: 10_000,
        closeButton: true,
      }),
    ])

    refresh.release()
    await expect
      .poll(() => view.queryClient.getQueryState(datasetKeys.list)?.fetchStatus)
      .toBe('idle')
    expect(apiRequests()).toEqual(['GET /datasets', 'DELETE /datasets/1', 'GET /datasets'])
  })

  it.each([
    ['the failure settles first', ['failure', 'success'] as const],
    ['the success settles first', ['success', 'failure'] as const],
  ])('keeps each overlapping delete to its own row when %s', async (_, order) => {
    deleteFails('2')
    const view = await renderCatalogue()
    const gates = { success: hold('DELETE'), failure: hold('DELETE') }
    const neverShown = view.neverShowsAgain('1')

    view.result.current.remove.mutate(customerTransactions)
    await gates.success.arrived
    view.result.current.remove.mutate(productInventory)
    await gates.failure.arrived
    await expect.poll(() => view.shownIds()).toEqual(['3'])

    const [first, second] = order
    gates[first].release()
    await expect.poll(() => view.shownIds()).toEqual(first === 'failure' ? ['2', '3'] : ['3'])

    gates[second].release()
    await expect.poll(() => view.shownIds()).toEqual(['2', '3'])
    await expect
      .poll(() => view.queryClient.isMutating({ mutationKey: datasetKeys.delete }))
      .toBe(0)
    expect(view.cachedIds()).toEqual(['2', '3'])
    expect(neverShown()).toBe(true)
    expect(toast.getToasts()).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ type: 'success', title: 'Deleted "Customer Transactions"' }),
        expect.objectContaining({ type: 'error', title: 'Couldn\'t delete "Product Inventory"' }),
      ]),
    )
  })

  it('cancels a refresh in flight before removing the row, so it never shows again', async () => {
    const view = await renderCatalogue()
    const deletion = hold('DELETE')
    view.result.current.remove.mutate(customerTransactions)
    await deletion.arrived
    const refresh = holdStaleRefresh()
    void view.queryClient.invalidateQueries({ queryKey: datasetKeys.list })
    await refresh.arrived
    const neverShown = view.neverShowsAgain('1')

    deletion.release()

    await expect.poll(() => view.result.current.remove.isSuccess).toBe(true)
    expect(view.cachedIds()).toEqual(['2', '3'])
    refresh.release()
    await expect
      .poll(() => view.queryClient.getQueryState(datasetKeys.list)?.fetchStatus)
      .toBe('idle')
    expect(view.cachedIds()).toEqual(['2', '3'])
    expect(neverShown()).toBe(true)
  })

  it("restarts a refresh it cancelled, so a failed delete's resync still reads the server", async () => {
    deleteFails('2')
    const view = await renderCatalogue()
    const success = hold('DELETE')
    view.result.current.remove.mutate(customerTransactions)
    await success.arrived
    const resync = holdStaleRefresh()
    view.result.current.remove.mutate(productInventory)
    await resync.arrived
    // Added elsewhere while the failed delete's resync was in flight.
    store.add(tradeConfirmations, keywordCurated(tradeConfirmations))

    success.release()

    await expect.poll(() => view.cachedIds()).toEqual(['2', '3', '4'])
    expect(apiRequests()).toEqual([
      'GET /datasets',
      'DELETE /datasets/1',
      'DELETE /datasets/2',
      'GET /datasets',
      'GET /datasets',
    ])
  })

  it('touches no list when none was loaded', async () => {
    const view = await renderHookWithProviders(() => useDeleteDataset())

    view.result.current.mutate(customerTransactions)

    await expect.poll(() => view.result.current.isSuccess).toBe(true)
    expect(view.queryClient.getQueryData(datasetKeys.list)).toBeUndefined()
    expect(apiRequests()).toEqual(['DELETE /datasets/1'])
  })
})
