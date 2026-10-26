import AxeBuilder from '@axe-core/playwright'
import {
  test as base,
  expect,
  type Locator,
  type Page,
  type Request,
  type Response,
  type Route,
} from '@playwright/test'
import type { components } from '../src/lib/api/schema.gen.ts'
import { apiUrl } from './urls.ts'

export { expect }

export type Dataset = components['schemas']['Dataset']
export type DatasetCreate = components['schemas']['DatasetCreate']

export const datasetsUrl = `${apiUrl}/datasets`

// The brief's test payload, as backend/scripts/verify_api.py sends it.
export const testPayload: DatasetCreate = {
  name: 'Trade Confirmations',
  owner: 'Middle Office',
  description:
    'Daily export of confirmed trades including instrument type, counterparty, notional value, and settlement date.',
}

export const seedNames = ['Customer Transactions', 'Product Inventory', 'Employee Directory']

export const failedCurationDetail = 'AI curation timed out.'

// An id the server's counter never produces, so the cleanup's DELETE for it is a harmless 404.
export const failedCurationDataset: Dataset = {
  ...testPayload,
  id: 'fulfilled-1',
  tags: [],
  summary: null,
  curation: { status: 'failed', provider: 'anthropic', detail: failedCurationDetail },
  createdAt: '2026-10-26T09:30:00Z',
}

interface CatalogueFixtures {
  /** Creates a dataset through the API, outside the page, and deletes it after the test. */
  createDataset: (payload?: DatasetCreate) => Promise<Dataset>
}

interface CleanupFixtures {
  createdDatasetIds: Set<string>
}

function isCreated(response: Response) {
  return (
    response.status() === 201 &&
    response.request().method() === 'POST' &&
    new URL(response.url()).pathname === '/datasets'
  )
}

/**
 * Every test starts from the three seeds without a reset endpoint: whatever a test created, through
 * the page or `createDataset`, is deleted through the public API afterwards. A 404 means the test
 * deleted it itself, or the response was faked with an id the server never had.
 */
export const test = base.extend<CatalogueFixtures & CleanupFixtures>({
  createdDatasetIds: [
    async ({ page, request }, use) => {
      const ids = new Set<string>()
      const bodies: Promise<void>[] = []
      page.on('response', (response) => {
        if (!isCreated(response)) return
        bodies.push(
          response.json().then((dataset: Dataset) => {
            ids.add(dataset.id)
          }),
        )
      })
      await use(ids)
      await Promise.all(bodies)
      for (const id of ids) {
        const response = await request.delete(`${datasetsUrl}/${encodeURIComponent(id)}`)
        expect([200, 404], `cleanup DELETE /datasets/${id}`).toContain(response.status())
      }
    },
    { auto: true },
  ],
  createDataset: async ({ request, createdDatasetIds }, use) => {
    await use(async (payload = testPayload) => {
      const response = await request.post(datasetsUrl, { data: payload })
      expect(response.status()).toBe(201)
      const dataset = (await response.json()) as Dataset
      createdDatasetIds.add(dataset.id)
      return dataset
    })
  },
})

/** Lets `respond` answer every `method` request to `url`; other methods go to the network. */
export async function routeApi(
  page: Page,
  method: string,
  url: string,
  respond: (route: Route) => Promise<void>,
): Promise<void> {
  await page.route(url, async (route) => {
    await (route.request().method() === method ? respond(route) : route.fallback())
  })
}

/**
 * Holds every `method` request to `url` until the returned function runs, then lets `respond`
 * answer it, so a test can assert a pending state without waiting on a timer.
 */
export async function holdRequests(
  page: Page,
  method: string,
  url: string,
  respond: (route: Route) => Promise<void> = (route) => route.continue(),
): Promise<() => void> {
  const gate = Promise.withResolvers<undefined>()
  await routeApi(page, method, url, async (route) => {
    await gate.promise
    await respond(route)
  })
  return () => {
    gate.resolve(undefined)
  }
}

/** Collects the page's requests to one API path, for asserting how many were sent. */
export function recordApiRequests(page: Page, method: string, pathname: string): Request[] {
  const requests: Request[] = []
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (request.method() === method && url.origin === apiUrl && url.pathname === pathname) {
      requests.push(request)
    }
  })
  return requests
}

/** Collects main-frame navigations, including same-document ones such as history changes. */
export function recordNavigations(page: Page): string[] {
  const navigations: string[] = []
  page.on('framenavigated', (frame) => {
    if (frame === page.mainFrame()) navigations.push(frame.url())
  })
  return navigations
}

export function toast(page: Page, title: string): Locator {
  return page
    .getByRole('region', { name: /^Notifications/ })
    .getByRole('listitem')
    .filter({ hasText: title })
}

/**
 * axe skips contrast checks on transparent elements, so a scan while a toast is still fading in
 * would pass without checking it. Waits until every toast is mounted and fully opaque.
 */
export async function waitForToastsToSettle(page: Page): Promise<void> {
  const toasts = page.locator('[data-sonner-toast]')
  await expect(toasts).not.toHaveCount(0)
  for (const settling of await toasts.all()) {
    await expect(settling).toHaveAttribute('data-mounted', 'true')
    await expect(settling).toHaveCSS('opacity', '1')
  }
}

export async function expectNoAxeViolations(page: Page): Promise<void> {
  const { violations } = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'])
    .analyze()
  expect(
    violations.map(({ id, nodes }) => ({
      id,
      targets: nodes.map(({ target }) => target.join(' ')),
    })),
  ).toEqual([])
}

/** Presses a key and checks focus did not fall to the body, where keyboard users lose their place. */
export async function press(page: Page, key: 'Tab' | 'Shift+Tab' | 'Enter' | 'Space' | 'Escape') {
  await page.keyboard.press(key)
  await expect(page.locator('body')).not.toBeFocused()
}

const maxTabStops = 30

/**
 * Tabs until `target`, located by role and accessible name, has focus. Matching the name rather
 * than counting tab stops keeps the test about what a user is looking for, not the page's layout.
 */
export async function tabTo(page: Page, target: Locator, key: 'Tab' | 'Shift+Tab' = 'Tab') {
  for (let stop = 0; stop < maxTabStops; stop += 1) {
    await press(page, key)
    if (await target.evaluate((element) => element === document.activeElement)) return
  }
  throw new Error(`${String(maxTabStops)} presses of ${key} never reached ${target.toString()}`)
}
