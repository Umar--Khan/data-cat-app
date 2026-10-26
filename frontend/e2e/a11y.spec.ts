import type { Page } from '@playwright/test'
import {
  datasetsUrl,
  expect,
  expectNoAxeViolations,
  failedCurationDataset,
  routeApi,
  seedNames,
  tabTo,
  test,
  testPayload,
  toast,
  waitForToastsToSettle,
} from './fixtures.ts'

async function loadCatalogue(page: Page) {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 3 })).toHaveText(seedNames)
}

async function submitTestPayload(page: Page) {
  await page.getByRole('textbox', { name: 'Name', exact: true }).fill(testPayload.name)
  await page.getByRole('textbox', { name: 'Owner', exact: true }).fill(testPayload.owner)
  await page
    .getByRole('textbox', { name: 'Description', exact: true })
    .fill(testPayload.description)
  await page.getByRole('button', { name: 'Add dataset', exact: true }).click()
}

async function expectNoHorizontalOverflow(page: Page) {
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }))
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth)
}

test.describe('axe (WCAG 2.2 A and AA, plus best practice)', () => {
  test('on load', async ({ page }) => {
    await loadCatalogue(page)
    await expectNoAxeViolations(page)
  })

  test('on the invalid form', async ({ page }) => {
    await loadCatalogue(page)
    await page.getByRole('button', { name: 'Add dataset', exact: true }).click()
    await expect(page.getByRole('textbox', { name: 'Name', exact: true })).toBeFocused()
    await expect(page.getByText('Enter a description', { exact: true })).toBeVisible()
    await expectNoAxeViolations(page)
  })

  test('after create, once the toast has settled', async ({ page }) => {
    await loadCatalogue(page)
    await submitTestPayload(page)
    await expect(toast(page, `Added "${testPayload.name}"`)).toBeVisible()
    await waitForToastsToSettle(page)
    await expectNoAxeViolations(page)
  })

  test('on a failed-curation row', async ({ page }) => {
    await routeApi(page, 'POST', datasetsUrl, (route) =>
      route.fulfill({ status: 201, json: failedCurationDataset }),
    )
    await loadCatalogue(page)
    await submitTestPayload(page)
    await expect(page.getByRole('article', { name: testPayload.name, exact: true })).toContainText(
      'Curation failed',
    )
    await waitForToastsToSettle(page)
    await expectNoAxeViolations(page)
  })

  test('with the delete dialog open', async ({ page }) => {
    await loadCatalogue(page)
    await page.getByRole('button', { name: 'Delete Customer Transactions', exact: true }).click()
    await expect(
      page.getByRole('alertdialog').getByRole('button', { name: 'Cancel', exact: true }),
    ).toBeFocused()
    await expectNoAxeViolations(page)
  })
})

test.describe('at 320 × 720', () => {
  test.use({ viewport: { width: 320, height: 720 } })

  test('reflows without horizontal scrolling and keeps the focused control clear of toasts', async ({
    page,
  }) => {
    await loadCatalogue(page)
    await expectNoHorizontalOverflow(page)

    await submitTestPayload(page)
    const added = toast(page, `Added "${testPayload.name}"`)
    await expect(added).toBeVisible()
    await expectNoHorizontalOverflow(page)

    // The new row's Delete button is the last control on the page, so it scrolls furthest down
    // towards the full-width toast stack.
    const lastControl = page.getByRole('button', {
      name: `Delete ${testPayload.name}`,
      exact: true,
    })
    await tabTo(page, lastControl)
    await expect(lastControl).toBeInViewport({ ratio: 1 })
    await expect
      .poll(() =>
        lastControl.evaluate((control) => {
          const box = control.getBoundingClientRect()
          const toasts = [...document.querySelectorAll('[data-sonner-toast]')].map((element) =>
            element.getBoundingClientRect(),
          )
          const topmost = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2)
          return {
            overlapsToast: toasts.some(
              (t) =>
                t.left < box.right &&
                box.left < t.right &&
                t.top < box.bottom &&
                box.top < t.bottom,
            ),
            onTop: topmost !== null && control.contains(topmost),
          }
        }),
      )
      .toEqual({ overlapsToast: false, onTop: true })
    // Still showing, so the check above measured against a toast rather than an empty stack.
    await expect(added).toBeVisible()
  })
})
