import { describe, expect, it } from 'vitest'
import { env, parseEnv } from './env'

describe('env', () => {
  it('reads the API base URL from the Vite environment', () => {
    expect(env.VITE_API_BASE_URL).toBe('http://api.test')
  })

  it.each(['http://localhost:8000', 'https://catalogue.example.com/api'])('accepts %s', (url) => {
    expect(parseEnv({ VITE_API_BASE_URL: url })).toEqual({ VITE_API_BASE_URL: url })
  })

  it.each([undefined, '', 'localhost:8000', 'ftp://example.com'])('rejects %j', (url) => {
    expect(() => parseEnv({ VITE_API_BASE_URL: url })).toThrow(/VITE_API_BASE_URL/)
  })

  it('says in English what is wrong with the variable', () => {
    expect(() => parseEnv({})).toThrow(
      'Invalid frontend environment.\n✖ Invalid input: expected string, received undefined\n  → at VITE_API_BASE_URL',
    )
    expect(() => parseEnv({ VITE_API_BASE_URL: 'localhost:8000' })).toThrow(
      'Invalid frontend environment.\n✖ Invalid URL\n  → at VITE_API_BASE_URL',
    )
  })
})
