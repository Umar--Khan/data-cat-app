import {
  datasetsUrl,
  expect,
  failedCurationDataset,
  failedCurationDetail,
  holdRequests,
  routeApi,
  seedNames,
  test,
  testPayload,
  toast,
} from './fixtures.ts'

// These fake the API with page.route because they test how the page reacts. The real backend's
// failure path is covered by `pnpm verify:api --degraded`.

test('an unreachable API on load shows the error, and Try again recovers', async ({ page }) => {
  await page.route(datasetsUrl, (route) => route.abort())
  await page.goto('/')

  const tryAgain = page.getByRole('button', { name: 'Try again', exact: true })
  // The list retries a network failure twice, with a 1 s then 2 s backoff, before it shows the error.
  await expect(tryAgain).toBeVisible({ timeout: 10_000 })
  await expect(
    page.getByText('Could not reach the server. Check your connection and try again.'),
  ).toBeVisible()
  await expect(page.getByRole('status').filter({ hasText: 'datasets' })).toHaveText(
    "Couldn't load datasets",
  )

  await page.unroute(datasetsUrl)
  const release = await holdRequests(page, 'GET', datasetsUrl)
  await tryAgain.click()

  await expect(page.getByRole('heading', { name: 'Datasets', exact: true })).toBeFocused()
  await expect(page.getByRole('status').filter({ hasText: 'datasets' })).toHaveText(
    'Loading datasets…',
  )
  await expect(tryAgain).toHaveCount(0)

  release()
  await expect(page.getByRole('heading', { level: 3 })).toHaveText(seedNames)
})

test('a POST answered with a curation-failed record shows the badge, the detail and a warning toast', async ({
  page,
}) => {
  await routeApi(page, 'POST', datasetsUrl, (route) =>
    route.fulfill({ status: 201, json: failedCurationDataset }),
  )
  await page.goto('/')
  await expect(page.getByRole('article')).toHaveCount(3)

  await page.getByRole('textbox', { name: 'Name', exact: true }).fill(testPayload.name)
  await page.getByRole('textbox', { name: 'Owner', exact: true }).fill(testPayload.owner)
  await page
    .getByRole('textbox', { name: 'Description', exact: true })
    .fill(testPayload.description)
  await page.getByRole('button', { name: 'Add dataset', exact: true }).click()

  const row = page.getByRole('article', { name: testPayload.name, exact: true })
  await expect(row).toContainText('Curation failed')
  await expect(row.getByText(failedCurationDetail, { exact: true })).toBeVisible()
  await expect(row.getByText('No tags', { exact: true })).toBeVisible()
  await expect(row.getByRole('list', { name: 'Tags' })).toHaveCount(0)

  const warning = toast(page, `Saved "${testPayload.name}" without AI tags`)
  await expect(warning).toBeVisible()
  await expect(warning).toContainText(failedCurationDetail)
  await expect(warning.getByRole('button', { name: 'Close toast' })).toBeVisible()
})

test('a delete answered with a 500 restores the row and shows an error toast', async ({
  page,
  createDataset,
}) => {
  const dataset = await createDataset()
  const message = 'The server hit an unexpected error.'
  const release = await holdRequests(page, 'DELETE', `${datasetsUrl}/${dataset.id}`, (route) =>
    route.fulfill({
      status: 500,
      contentType: 'application/problem+json',
      json: {
        type: 'about:blank',
        title: 'Internal Server Error',
        status: 500,
        detail: message,
        instance: `/datasets/${dataset.id}`,
        errors: [],
      },
    }),
  )
  await page.goto('/')
  const row = page.getByRole('article', { name: dataset.name, exact: true })
  await expect(row).toBeVisible()

  await page.getByRole('button', { name: `Delete ${dataset.name}`, exact: true }).click()
  await page
    .getByRole('alertdialog', { name: `Delete "${dataset.name}"?` })
    .getByRole('button', { name: 'Delete dataset', exact: true })
    .click()
  await expect(row).toHaveCount(0)

  release()
  await expect(row).toBeVisible()
  await expect(page.getByRole('heading', { level: 3 })).toHaveText([...seedNames, dataset.name])
  const error = toast(page, `Couldn't delete "${dataset.name}"`)
  await expect(error).toBeVisible()
  await expect(error).toContainText(message)
  await expect(error.getByRole('button', { name: 'Close toast' })).toBeVisible()
})
