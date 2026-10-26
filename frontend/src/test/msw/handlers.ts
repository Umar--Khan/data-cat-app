import { http, HttpResponse } from 'msw'
import type { Dataset, DatasetCreate, FieldError, ProblemDetails } from '@/lib/api/schema.gen'
import { env } from '@/lib/env'
import { keywordCurated, store, type Curated } from './store'

export function apiUrl(path: string): string {
  return `${env.VITE_API_BASE_URL}${path}`
}

export function problem(body: ProblemDetails) {
  return HttpResponse.json(body, {
    status: body.status,
    headers: { 'Content-Type': 'application/problem+json' },
  })
}

export function serverError(instance: string) {
  return problem({
    type: 'about:blank',
    title: 'Internal Server Error',
    status: 500,
    detail: 'The server hit an unexpected error.',
    instance,
    errors: [],
  })
}

export function invalidBody(errors: FieldError[]) {
  const fields = errors.map(({ field }) => field).join(', ')
  return problem({
    type: '/problems/validation-error',
    title: 'Invalid request body',
    status: 400,
    detail: `The request body has ${errors.length === 1 ? 'an invalid field' : 'invalid fields'}: ${fields}.`,
    instance: '/datasets',
    errors,
  })
}

// Typed by the schema, so renaming a field fails tsc here as well as in the app.
const maxLengths: Record<keyof DatasetCreate, number> = {
  name: 120,
  owner: 120,
  description: 2000,
}

function isField(field: string): field is keyof DatasetCreate {
  return Object.hasOwn(maxLengths, field)
}

function fieldMessage(value: unknown, maxLength: number): string | undefined {
  if (value === undefined) return 'This field is required.'
  if (typeof value !== 'string') return 'This field must be a string.'
  // Code points after trimming, as the API counts them.
  const length = Array.from(value.trim()).length
  if (length === 0) return 'This field must not be blank.'
  if (length > maxLength) return `This field must be at most ${String(maxLength)} characters.`
}

async function readObject(request: Request): Promise<Record<string, unknown> | undefined> {
  const body: unknown = await request.json().catch(() => undefined)
  if (typeof body === 'object' && body !== null && !Array.isArray(body)) {
    return body as Record<string, unknown>
  }
}

/** POST /datasets with the API's validation, storing the record with the given curation. */
export async function createDataset(request: Request, curate: (input: DatasetCreate) => Curated) {
  const body = await readObject(request)
  if (!body) {
    return problem({
      type: '/problems/malformed-body',
      title: 'Malformed request body',
      status: 400,
      detail: 'The request body must be a JSON object sent as application/json.',
      instance: '/datasets',
      errors: [],
    })
  }
  const errors: FieldError[] = []
  for (const [field, maxLength] of Object.entries(maxLengths)) {
    const message = fieldMessage(body[field], maxLength)
    if (message) errors.push({ field, message })
  }
  for (const field of Object.keys(body).filter((field) => !isField(field))) {
    errors.push({ field, message: 'This field is not allowed.' })
  }
  if (errors.length > 0) return invalidBody(errors)

  const trimmed = (field: keyof DatasetCreate) => String(body[field]).trim()
  const input = {
    name: trimmed('name'),
    owner: trimmed('owner'),
    description: trimmed('description'),
  }
  const dataset = store.add(input, curate(input))
  return HttpResponse.json<Dataset>(dataset, {
    status: 201,
    headers: { Location: `/datasets/${dataset.id}` },
  })
}

export const handlers = [
  http.get(apiUrl('/datasets'), () => HttpResponse.json<Dataset[]>(store.list())),
  http.post(apiUrl('/datasets'), ({ request }) => createDataset(request, keywordCurated)),
  http.delete<{ id: string }>(apiUrl('/datasets/:id'), ({ params: { id } }) => {
    const removed = store.remove(id)
    if (removed) return HttpResponse.json<Dataset>(removed)
    return problem({
      type: '/problems/dataset-not-found',
      title: 'Dataset not found',
      status: 404,
      detail: `No dataset has id "${id}". It may have been deleted already.`,
      instance: `/datasets/${encodeURIComponent(id)}`,
      errors: [],
    })
  }),
]
