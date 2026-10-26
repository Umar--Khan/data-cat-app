import { setupWorker } from 'msw/browser'
import { HttpNetworkFrame } from 'msw/experimental'
import { env } from '@/lib/env'
import { handlers } from './handlers'
import { store } from './store'

const apiOrigin = new URL(env.VITE_API_BASE_URL).origin

function isApiRequest(request: Request): boolean {
  return new URL(request.url).origin === apiOrigin
}

export const worker = setupWorker(...handlers)

const requestLog: string[] = []

worker.events.on('request:start', ({ request }) => {
  if (isApiRequest(request)) requestLog.push(`${request.method} ${new URL(request.url).pathname}`)
})

/** Every request the mock API has received in the current test, as "METHOD /path", in order. */
export function apiRequests(): string[] {
  return [...requestLog]
}

export async function startMockApi(): Promise<void> {
  await worker.start({
    quiet: true,
    // Scoped to the API: the test runner's own module and asset requests go through this worker
    // too. Throwing makes MSW answer a missing handler at once with a 500 and a console error that
    // names the request, instead of passing it through to a host that never resolves.
    onUnhandledFrame({ frame, defaults }) {
      if (frame instanceof HttpNetworkFrame && isApiRequest(frame.data.request)) {
        defaults.error()
        throw new Error('The mock API has no handler for this request.')
      }
    },
  })
}

export function resetMockApi(): void {
  worker.resetHandlers()
  store.reset()
  requestLog.length = 0
}
