import { z } from 'zod'
import type { FieldError, ProblemDetails } from '@/lib/api/schema.gen'

export const networkErrorMessage =
  'Could not reach the server. Check your connection and try again.'

export const unreadableResponseMessage = 'The server sent a response this app could not read.'

const problemMediaType = 'application/problem+json'

interface ApiErrorInit {
  status: number | null
  message: string
  fieldErrors?: readonly FieldError[]
  cause?: unknown
}

export class ApiError extends Error {
  override readonly name = 'ApiError'
  /** The HTTP status, or null when no response arrived or its body could not be read. */
  readonly status: number | null
  readonly fieldErrors: readonly FieldError[]

  constructor({ status, message, fieldErrors = [], cause }: ApiErrorInit) {
    super(message, { cause })
    this.status = status
    this.fieldErrors = fieldErrors
  }

  static fromResponse(response: Response, body: unknown): ApiError {
    const problem = readProblem(response, body)
    return new ApiError({
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
 * Resolves an openapi-fetch call to its data, or throws an ApiError for an error response, a
 * network failure or a success response whose body is not JSON.
 *
 * fetch rejects with a TypeError when no response arrives. openapi-fetch parses error bodies
 * leniently but a 2xx body strictly, so a proxy's sign-in page or a static host's index.html
 * served with a 200 surfaces as a SyntaxError whose text means nothing to a user. Anything else is
 * rethrown untouched, an AbortError above all: a request cancelled on purpose is not a failure to
 * report.
 */
export async function unwrap<TData>(request: Promise<FetchResult<TData>>): Promise<TData> {
  let result: FetchResult<TData>
  try {
    result = await request
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiError({ status: null, message: networkErrorMessage, cause: error })
    }
    if (error instanceof SyntaxError) {
      throw new ApiError({ status: null, message: unreadableResponseMessage, cause: error })
    }
    throw error
  }
  if (!result.response.ok) throw ApiError.fromResponse(result.response, result.error)
  // openapi-fetch leaves data undefined only for an empty 2xx body, which no operation sends.
  return result.data as TData
}
