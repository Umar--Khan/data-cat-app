import { z } from 'zod'
import type { FieldError, ProblemDetails } from '@/lib/api/schema.gen'

export const networkErrorMessage =
  'Could not reach the server. Check your connection and try again.'

const problemMediaType = 'application/problem+json'

interface ApiErrorInit {
  kind: 'http' | 'network'
  status: number | null
  message: string
  fieldErrors?: readonly FieldError[]
  cause?: unknown
}

export class ApiError extends Error {
  override readonly name = 'ApiError'
  readonly kind: 'http' | 'network'
  /** The HTTP status, or null when no response arrived. */
  readonly status: number | null
  readonly fieldErrors: readonly FieldError[]

  constructor({ kind, status, message, fieldErrors = [], cause }: ApiErrorInit) {
    super(message, { cause })
    this.kind = kind
    this.status = status
    this.fieldErrors = fieldErrors
  }

  static fromResponse(response: Response, body: unknown): ApiError {
    const problem = readProblem(response, body)
    return new ApiError({
      kind: 'http',
      status: response.status,
      message: problem
        ? problem.detail || problem.title
        : `The server returned an unexpected error (HTTP ${String(response.status)}).`,
      fieldErrors: problem?.errors,
    })
  }
}

const problemFields = z.object({
  title: z.string(),
  detail: z.string(),
  errors: z.array(z.object({ field: z.string(), message: z.string() })),
}) satisfies z.ZodType<Pick<ProblemDetails, 'title' | 'detail' | 'errors'>>

type ProblemFields = z.infer<typeof problemFields>

// openapi-fetch parses any error body that is valid JSON and types it as the documented problem,
// but a proxy or a crashed server can answer with anything, so the body is checked before use,
// down to each field error.
function readProblem(response: Response, body: unknown): ProblemFields | undefined {
  const mediaType = response.headers.get('Content-Type')?.split(';')[0]?.trim().toLowerCase()
  if (mediaType !== problemMediaType) return
  const parsed = problemFields.safeParse(body)
  return parsed.success ? parsed.data : undefined
}

interface FetchResult<TData> {
  data?: TData
  error?: unknown
  response: Response
}

/**
 * Resolves an openapi-fetch call to its data, or throws an ApiError for an error response or a
 * network failure.
 *
 * fetch rejects with a TypeError when no response arrives. Anything else is rethrown untouched,
 * an AbortError above all: a request cancelled on purpose is not a failure to report.
 */
export async function unwrap<TData>(request: Promise<FetchResult<TData>>): Promise<TData> {
  let result: FetchResult<TData>
  try {
    result = await request
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiError({
        kind: 'network',
        status: null,
        message: networkErrorMessage,
        cause: error,
      })
    }
    throw error
  }
  if (!result.response.ok) throw ApiError.fromResponse(result.response, result.error)
  // openapi-fetch leaves data undefined only for an empty 2xx body, which no operation sends.
  return result.data as TData
}
