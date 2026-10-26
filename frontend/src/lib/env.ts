import { en } from 'zod/locales'
import * as z from 'zod/mini'

// zod/mini ships no messages, so a bad env would report only "Invalid input" rather than, say,
// "Invalid URL". The locale is global; it is set here because this module parses as it loads.
z.config(en())

// http(s) only: `new URL('localhost:8000')` parses, with "localhost:" as the protocol.
const envSchema = z.object({
  VITE_API_BASE_URL: z.url({ protocol: /^https?$/ }),
})

export type Env = z.infer<typeof envSchema>

export function parseEnv(source: unknown): Env {
  const result = envSchema.safeParse(source)
  if (!result.success) {
    throw new Error(`Invalid frontend environment.\n${z.prettifyError(result.error)}`)
  }
  return result.data
}

export const env = parseEnv(import.meta.env)
