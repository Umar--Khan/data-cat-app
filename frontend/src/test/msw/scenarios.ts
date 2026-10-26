import { http, type HttpResponseResolver, type PathParams } from 'msw'
import { onTestFinished } from 'vitest'
import type { FieldError } from '@/lib/api/schema.gen'
import { apiUrl, createDataset, invalidBody, serverError } from './handlers'
import { failedCuration, store } from './store'
import { worker } from './worker'

type Method = 'GET' | 'POST' | 'DELETE'

export interface Gate {
  /** Resolves with the held request once it reaches the mock API. */
  readonly arrived: Promise<Request>
  /** Lets the held request go on to whichever handler answers it. */
  release: () => void
}

interface WaitingGate {
  method: Method
  arrive: (request: Request) => void
  released: Promise<void>
}

const waiting: WaitingGate[] = []

// One handler holds every gated request, so gates are claimed in the order hold() was called.
const gatekeeper = http.all(apiUrl('/*'), async ({ request }) => {
  const gate = waiting.find(({ method }) => method === request.method)
  if (!gate) return
  waiting.splice(waiting.indexOf(gate), 1)
  gate.arrive(request)
  await gate.released
})

/**
 * Holds the next request with this method that has no gate yet, until the test releases it.
 * Call it once per request to hold; overlapping requests claim gates in call order.
 */
export function hold(method: Method): Gate {
  let arrive: (request: Request) => void = () => undefined
  let release: () => void = () => undefined
  const arrived = new Promise<Request>((resolve) => (arrive = resolve))
  const released = new Promise<void>((resolve) => (release = resolve))
  const gate = { method, arrive, released }
  waiting.push(gate)
  onTestFinished(() => {
    if (waiting.includes(gate)) waiting.splice(waiting.indexOf(gate), 1)
  })
  worker.use(gatekeeper)
  return { arrived, release }
}

/**
 * Puts a handler ahead of the defaults until the returned stop function runs or the test ends.
 * The gatekeeper stays in front of it, so hold() delays whichever handler answers, whatever order
 * the test set them up in. A resolver that returns nothing falls through to the next handler.
 */
function scenario<Params extends PathParams<keyof Params>>(
  method: 'get' | 'post' | 'delete',
  path: string,
  resolver: HttpResponseResolver<Params>,
): () => void {
  let active = true
  worker.use(
    gatekeeper,
    http[method]<Params>(apiUrl(path), (info) => (active ? resolver(info) : undefined)),
  )
  return () => {
    active = false
  }
}

/** GET /datasets answers 500 problems, every retry included. */
export function listFails() {
  return scenario('get', '/datasets', () => serverError('/datasets'))
}

/** POST /datasets answers a 400 validation problem with these field errors. */
export function createInvalid(fieldErrors: FieldError[]) {
  return scenario('post', '/datasets', () => invalidBody(fieldErrors))
}

/** POST /datasets stores the record with failed curation and answers 201, as the API does. */
export function createCurationFailed() {
  return scenario('post', '/datasets', ({ request }) =>
    createDataset(request, () => failedCuration),
  )
}

/** DELETE of this id, or of any id, answers a 500 problem and deletes nothing. */
export function deleteFails(id?: string) {
  return scenario<{ id: string }>('delete', '/datasets/:id', ({ params }) =>
    id === undefined || params.id === id ? serverError(`/datasets/${params.id}`) : undefined,
  )
}

/** The record is deleted elsewhere just before DELETE of this id, or of any id, arrives: a 404. */
export function deleteNotFound(id?: string) {
  return scenario<{ id: string }>('delete', '/datasets/:id', ({ params }) => {
    if (id === undefined || params.id === id) store.remove(params.id)
  })
}
