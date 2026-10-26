import createClient from 'openapi-fetch'
import type { paths } from '@/lib/api/schema.gen'
import { env } from '@/lib/env'

// The default media type (`${string}/${string}`) is kept on purpose: narrowing it to
// `${string}/json` would drop error bodies, which are typed under application/problem+json.
export const apiClient = createClient<paths>({ baseUrl: env.VITE_API_BASE_URL })
