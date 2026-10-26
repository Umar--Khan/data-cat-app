import {
  datasetsUrl,
  expect,
  holdRequests,
  recordApiRequests,
  recordNavigations,
  seedNames,
  test,
  testPayload,
  toast,
  type Dataset,
} from './fixtures.ts'

declare global {
  interface Window {
    e2eSentinel?: string
  }
}

// One test per item of the brief's frontend checklist, in its words.

test('Page loads showing all three pre-loaded datasets', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('article')).toHaveCount(3)
  await expect(page.getByRole('heading', { level: 3 })).toHaveText(seedNames)
  for (const name of seedNames) {
    await expect(page.getByRole('article', { name, exact: true })).toContainText('Sample data')
  }
})

test('Submitting the test payload adds a fourth entry to the list with tags and summary visible', async ({
  page,
}) => {
  const posts = recordApiRequests(page, 'POST', '/datasets')
  const release = await holdRequests(page, 'POST', datasetsUrl)
  await page.goto('/')
  await expect(page.getByRole('article')).toHaveCount(3)

  const name = page.getByRole('textbox', { name: 'Name', exact: true })
  const owner = page.getByRole('textbox', { name: 'Owner', exact: true })
  const description = page.getByRole('textbox', { name: 'Description', exact: true })
  await name.fill(testPayload.name)
  await owner.fill(testPayload.owner)
  await description.fill(testPayload.description)
  await page.getByRole('button', { name: 'Add dataset', exact: true }).click()

  await test.step('pending while the POST is held', async () => {
    const pending = page.getByRole('button', { name: 'Saving and curating…', exact: true })
    await expect(pending).toHaveAttribute('aria-disabled', 'true')
    await expect(pending).toBeFocused()
    await expect(page.getByRole('status').filter({ hasText: 'Generating' })).toHaveText(
      'Generating tags and a summary. This can take up to 20 seconds.',
    )
    for (const field of [name, owner, description]) await expect(field).not.toBeEditable()
    // Ignored while pending: POST is not idempotent. The count is checked once the page settles.
    await page.keyboard.press('Enter')
  })

  // Registered only now: the gate holds the response until release, so it cannot be missed.
  const created = page.waitForResponse(
    (response) => response.url() === datasetsUrl && response.request().method() === 'POST',
  )
  release()
  const record = (await (await created).json()) as Dataset

  const rows = page.getByRole('article')
  await expect(rows).toHaveCount(4)
  const row = rows.last()
  await expect(row.getByRole('heading', { level: 3 })).toHaveText(testPayload.name)
  await expect(row.getByRole('definition')).toHaveText(testPayload.owner)
  await expect(row).toContainText('Keyword curated')
  expect(record.tags).not.toHaveLength(0)
  await expect(row.getByRole('list', { name: 'Tags' }).getByRole('listitem')).toHaveText(
    record.tags,
  )
  expect(record.summary).not.toBeNull()
  await expect(row.getByText(String(record.summary), { exact: true })).toBeVisible()
  await expect(toast(page, `Added "${testPayload.name}"`)).toBeVisible()

  await expect(page.getByRole('button', { name: 'Add dataset', exact: true })).toBeVisible()
  await expect(name).toBeFocused()
  for (const field of [name, owner, description]) await expect(field).toHaveValue('')
  expect(posts).toHaveLength(1)
})

test('Deleting an entry removes it from the list without a page refresh', async ({
  page,
  request,
  createDataset,
}) => {
  const dataset = await createDataset()
  await page.goto('/')
  await expect(page.getByRole('article')).toHaveCount(4)
  await page.evaluate(() => {
    window.e2eSentinel = 'same document'
  })
  const navigations = recordNavigations(page)

  await page.getByRole('button', { name: `Delete ${dataset.name}`, exact: true }).click()
  await page
    .getByRole('alertdialog', { name: `Delete "${dataset.name}"?` })
    .getByRole('button', { name: 'Delete dataset', exact: true })
    .click()

  await expect(page.getByRole('article', { name: dataset.name, exact: true })).toHaveCount(0)
  await expect(toast(page, `Deleted "${dataset.name}"`)).toBeVisible()
  await expect(page.getByRole('heading', { level: 3 })).toHaveText(seedNames)
  expect(await page.evaluate(() => window.e2eSentinel)).toBe('same document')
  expect(navigations).toEqual([])

  const remaining = (await (await request.get(datasetsUrl)).json()) as Dataset[]
  expect(remaining.map(({ name }) => name)).toEqual(seedNames)
})

test('Submitting the form with an empty name or description shows an inline error message', async ({
  page,
}) => {
  const posts = recordApiRequests(page, 'POST', '/datasets')
  await page.goto('/')
  const name = page.getByRole('textbox', { name: 'Name', exact: true })
  const description = page.getByRole('textbox', { name: 'Description', exact: true })
  const submit = page.getByRole('button', { name: 'Add dataset', exact: true })

  await test.step('empty name', async () => {
    await page.getByRole('textbox', { name: 'Owner', exact: true }).fill(testPayload.owner)
    await description.fill(testPayload.description)
    await submit.click()

    await expect(page.getByText('Enter a name', { exact: true })).toBeVisible()
    await expect(name).toBeFocused()
    await expect(name).toHaveAttribute('aria-invalid', 'true')
    await expect(name).toHaveAccessibleDescription('Enter a name')
  })

  await test.step('empty description', async () => {
    await name.fill(testPayload.name)
    await description.fill('')
    await submit.click()

    await expect(page.getByText('Enter a description', { exact: true })).toBeVisible()
    await expect(description).toBeFocused()
    await expect(description).toHaveAttribute('aria-invalid', 'true')
    await expect(description).toHaveAccessibleDescription(/Enter a description$/)
    await expect(name).not.toHaveAttribute('aria-invalid')
  })

  expect(posts).toHaveLength(0)
})
