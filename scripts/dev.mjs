import { setTimeout as sleep } from 'node:timers/promises'
import { concurrently } from 'concurrently'

const degraded = process.argv.includes('--degraded')
const apiPort = degraded ? 8100 : 8000
const webPort = degraded ? 5180 : 5173
const apiUrl = `http://localhost:${apiPort}`
const webUrl = `http://localhost:${webPort}`

// The real Anthropic provider pointed at a closed local port: every curation fails as
// "unavailable" within a second and nothing leaves the machine. Ports differ so this
// profile can run beside `pnpm dev`.
const apiEnv = degraded
  ? {
      CATALOGUE_CURATION_PROVIDER: 'anthropic',
      ANTHROPIC_API_KEY: 'offline',
      ANTHROPIC_BASE_URL: 'http://127.0.0.1:9',
      CATALOGUE_CORS_ORIGINS: JSON.stringify([webUrl]),
    }
  : {}
const webEnv = degraded ? { VITE_API_BASE_URL: apiUrl } : {}

// A server left running on the API port would answer the health poll below, and the banner
// would report its curation provider before uvicorn failed to bind.
const occupied = await fetch(`${apiUrl}/health`, { signal: AbortSignal.timeout(500) }).then(
  () => true,
  () => false,
)
if (occupied) {
  console.error(`Something is already listening on ${apiUrl}. Stop it, then run this again.`)
  process.exit(1)
}

const { result } = concurrently(
  [
    {
      name: 'api',
      prefixColor: 'blue',
      // exec, not uv run: uv forwarding SIGTERM to an already-exited child prints an ESRCH error on Ctrl-C.
      command: `uv sync --quiet && exec .venv/bin/uvicorn catalogue.app:create_app --factory --reload --reload-dir src --port ${apiPort}`,
      cwd: 'backend',
      env: apiEnv,
    },
    {
      name: 'web',
      prefixColor: 'magenta',
      command: `pnpm --filter frontend exec vite --port ${webPort} --strictPort`,
      env: webEnv,
    },
  ],
  { killOthersOn: ['failure', 'success'] },
)

const exitCode = result.then(
  () => 0,
  () => 1,
)
const stopPolling = new AbortController()
exitCode.then(() => stopPolling.abort())

async function poll(url, read, signal) {
  const deadline = Date.now() + 30_000
  while (Date.now() < deadline && !signal.aborted) {
    const value = await fetch(url, {
      signal: AbortSignal.any([signal, AbortSignal.timeout(1_000)]),
    })
      .then((response) => (response.ok ? read(response) : null))
      .catch(() => null)
    if (value) return value
    await sleep(500, undefined, { signal }).catch(() => {})
  }
  return null
}

// Waiting for Vite as well keeps the banner below its ready block instead of buried above it.
const [health, webReady] = await Promise.all([
  poll(`${apiUrl}/health`, (response) => response.json(), stopPolling.signal),
  poll(webUrl, () => true, stopPolling.signal),
])
if (health && webReady) {
  console.log(
    `\n  Data catalogue: ${webUrl}  ·  curation provider: ${health.curationProvider}  ·  API docs: ${apiUrl}/docs\n`,
  )
} else if (!stopPolling.signal.aborted) {
  const silent = [!health && `[api] ${apiUrl}/health`, !webReady && `[web] ${webUrl}`]
  console.warn(
    `\n  No answer within 30 s from ${silent.filter(Boolean).join(' or ')}; see its output above.\n`,
  )
}

process.exitCode = await exitCode
