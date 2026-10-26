import { toast } from 'sonner'
import { describe, expect, it, onTestFinished } from 'vitest'
import { page, userEvent } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { datasetFieldLimits } from '@/features/datasets/components/dataset-form-schema'
import { networkErrorMessage } from '@/lib/api/api-error'
import type { Dataset, DatasetCreate } from '@/lib/api/schema.gen'
import { expectNoA11yViolations } from '@/test/a11y'
import { emulateMedia } from '@/test/emulate-media'
import { hold } from '@/test/msw/scenarios'
import { seedDatasets, store } from '@/test/msw/store'
import { apiRequests } from '@/test/msw/worker'
import indexHtml from '../../index.html?raw'
import { App } from './app'
import { Providers } from './providers'

const [customerTransactions, productInventory, employeeDirectory] = seedDatasets as [
  Dataset,
  Dataset,
  Dataset,
]

// The brief's test payload.
const tradeConfirmations: DatasetCreate = {
  name: 'Trade Confirmations',
  owner: 'Middle Office',
  description:
    'Daily export of confirmed trades including instrument type, counterparty, notional value, and settlement date.',
}

/** A name as long as the API allows, in words that wrap as a real name would. */
function longestName(index: number): string {
  return `Regional settlement reconciliation extract ${String(index)} `
    .repeat(4)
    .slice(0, datasetFieldLimits.name)
}

/** The page as main.tsx mounts it, with the real providers and toaster. */
async function renderApp() {
  const screen = await render(
    <Providers>
      <App />
    </Providers>,
  )
  const form = screen.getByRole('region', { name: 'Add a dataset', exact: true })
  const list = screen.getByRole('region', { name: 'Datasets', exact: true })
  return Object.assign(screen, {
    form,
    list,
    field: {
      name: form.getByRole('textbox', { name: 'Name' }),
      owner: form.getByRole('textbox', { name: 'Owner' }),
      description: form.getByRole('textbox', { name: 'Description' }),
    },
    addButton: form.getByRole('button', { name: 'Add dataset' }),
    datasetsHeading: list.getByRole('heading', { level: 2, name: 'Datasets' }),
    row: (name: string) => list.getByRole('article', { name }),
    rowHeading: (name: string) => list.getByRole('heading', { level: 3, name }),
    rowNames: () =>
      list
        .getByRole('heading', { level: 3 })
        .elements()
        .map((heading) => heading.textContent),
  })
}

async function renderLoaded() {
  const screen = await renderApp()
  await expect.element(screen.row(employeeDirectory.name)).toBeVisible()
  return screen
}

/** Waits for a toast to fade in fully, because axe skips transparent text but not half-faded. */
async function expectToast(title: string) {
  const text = page
    .getByRole('region', { name: 'Notifications alt+T' })
    .getByText(title, { exact: true })
  await expect.element(text).toBeVisible()
  const toast = text.element().closest('[data-sonner-toast]')
  if (!toast) throw new Error(`"${title}" is not in a toast`)
  await expect.poll(() => getComputedStyle(toast).opacity).toBe('1')
}

describe("The brief's frontend checklist", () => {
  it('Page loads showing all three pre-loaded datasets', async () => {
    const gate = hold('GET')
    const screen = await renderApp()
    await gate.arrived

    await expect.element(screen.list.getByRole('status')).toHaveTextContent('Loading datasets…')
    await expectNoA11yViolations()

    gate.release()
    await expect.element(screen.row(employeeDirectory.name)).toBeVisible()
    expect(screen.rowNames()).toEqual([
      customerTransactions.name,
      productInventory.name,
      employeeDirectory.name,
    ])
    await expectNoA11yViolations()
  })

  it('Submitting the test payload above adds a fourth entry to the list with tags and summary visible', async () => {
    const gate = hold('POST')
    const screen = await renderLoaded()

    await userEvent.fill(screen.field.name, tradeConfirmations.name)
    await userEvent.fill(screen.field.owner, tradeConfirmations.owner)
    await userEvent.fill(screen.field.description, tradeConfirmations.description)
    await userEvent.click(screen.addButton)

    const request = await gate.arrived
    expect(await request.clone().json()).toEqual(tradeConfirmations)
    await expect
      .element(screen.form.getByRole('button', { name: 'Saving and curating…' }))
      .toHaveAttribute('aria-disabled', 'true')
    await expect
      .element(screen.form.getByRole('status'))
      .toHaveTextContent('Generating tags and a summary. This can take up to 20 seconds.')
    await expectNoA11yViolations()

    gate.release()
    const added = screen.row(tradeConfirmations.name)
    await expect.element(added).toBeVisible()
    expect(screen.rowNames()).toEqual([
      customerTransactions.name,
      productInventory.name,
      employeeDirectory.name,
      tradeConfirmations.name,
    ])
    await expect.element(added.getByRole('list', { name: 'Tags' })).toHaveTextContent('catalogue')
    await expect.element(added.getByText('A dataset named Trade Confirmations.')).toBeVisible()
    await expect.element(added.getByText('Keyword curated')).toBeVisible()
    await expect.element(screen.field.name).toHaveFocus()
    await expect.element(screen.field.name).toHaveValue('')
    await expectToast('Added "Trade Confirmations"')
    // The 201 body is appended to the list, so nothing is fetched again.
    expect(apiRequests()).toEqual(['GET /datasets', 'POST /datasets'])
    await expectNoA11yViolations()
  })

  it('Deleting an entry removes it from the list without a page refresh', async () => {
    const screen = await renderLoaded()

    await userEvent.click(
      screen.list.getByRole('button', { name: `Delete ${productInventory.name}` }),
    )
    const dialog = page.getByRole('alertdialog', { name: `Delete "${productInventory.name}"?` })
    await expect.element(dialog).toBeVisible()
    await expectNoA11yViolations()

    await userEvent.click(dialog.getByRole('button', { name: 'Delete dataset' }))
    await expect.element(screen.row(productInventory.name)).not.toBeInTheDocument()
    expect(screen.rowNames()).toEqual([customerTransactions.name, employeeDirectory.name])
    await expect.element(screen.rowHeading(employeeDirectory.name)).toHaveFocus()
    await expectToast(`Deleted "${productInventory.name}"`)
    // A reload would have fetched the list again.
    expect(apiRequests()).toEqual(['GET /datasets', 'DELETE /datasets/2'])
    await expectNoA11yViolations()
  })

  it('Submitting the form with an empty name or description shows an inline error message', async () => {
    const screen = await renderLoaded()

    await userEvent.click(screen.addButton)
    await expect.element(screen.field.name).toHaveFocus()
    await expect.element(screen.field.name).toHaveAttribute('aria-invalid', 'true')
    await expect.element(screen.field.name).toHaveAccessibleDescription('Enter a name')
    await expect
      .element(screen.field.description)
      .toHaveAccessibleDescription(
        'What the data contains and how often it updates. Used to generate tags and a summary. Enter a description',
      )
    await expectNoA11yViolations()

    await userEvent.fill(screen.field.name, tradeConfirmations.name)
    await userEvent.fill(screen.field.owner, tradeConfirmations.owner)
    await userEvent.click(screen.addButton)
    await expect.element(screen.field.description).toHaveFocus()
    await expect.element(screen.field.name).not.toHaveAttribute('aria-invalid')
    await expect.element(screen.field.description).toHaveAttribute('aria-invalid', 'true')

    expect(apiRequests()).toEqual(['GET /datasets'])
    expect(screen.rowNames()).toHaveLength(3)
    await expectNoA11yViolations()
  })
})

describe('App', () => {
  it('has a banner with the h1, then a main with a labelled section per h2, and no skipped levels', async () => {
    const screen = await renderLoaded()

    const banner = screen.getByRole('banner')
    await expect
      .element(banner.getByRole('heading', { level: 1, name: 'Data Catalogue' }))
      .toBeVisible()
    await expect
      .element(banner.getByText('Register a dataset to get tags and a one-sentence summary.'))
      .toBeVisible()
    const main = screen.getByRole('main')
    await expect.element(main).toContainElement(screen.form.element())
    await expect.element(main).toContainElement(screen.list.element())
    await expect
      .element(screen.form.getByRole('heading', { level: 2, name: 'Add a dataset' }))
      .toBeVisible()
    await expect.element(screen.datasetsHeading).toHaveAttribute('tabindex', '-1')

    const outline = screen
      .getByRole('heading')
      .elements()
      .map((heading) => `${heading.tagName} ${heading.textContent}`)
    expect(outline).toEqual([
      'H1 Data Catalogue',
      'H2 Add a dataset',
      'H2 Datasets',
      `H3 ${customerTransactions.name}`,
      `H3 ${productInventory.name}`,
      `H3 ${employeeDirectory.name}`,
    ])
    await expectNoA11yViolations()
  })

  it('is titled Data Catalogue, in English', () => {
    // The test runner serves its own page, so the app's index.html is read as text.
    const document = new DOMParser().parseFromString(indexHtml, 'text/html')

    expect(document.title).toBe('Data Catalogue')
    expect(document.documentElement.lang).toBe('en')
  })

  it('starts with a skip link that moves focus to the Datasets heading', async () => {
    const screen = await renderLoaded()
    const skipLink = screen.getByRole('link', { name: 'Skip to datasets' })
    expect(skipLink.element().getBoundingClientRect().width).toBe(1)

    await userEvent.tab()
    await expect.element(skipLink).toHaveFocus()
    await expect.element(skipLink).toBeVisible()
    expect(skipLink.element().getBoundingClientRect().width).toBeGreaterThan(1)
    await expectNoA11yViolations()

    await userEvent.keyboard('{Enter}')
    await expect.element(screen.datasetsHeading).toHaveFocus()
    // Sequential focus carries on from the heading, past the form.
    await userEvent.tab()
    await expect
      .element(screen.list.getByRole('button', { name: `Delete ${customerTransactions.name}` }))
      .toHaveFocus()
  })

  it('moves focus to its Datasets heading when the last dataset is deleted', async () => {
    store.reset([customerTransactions])
    const screen = await renderApp()
    await expect.element(screen.row(customerTransactions.name)).toBeVisible()

    await userEvent.click(
      screen.list.getByRole('button', { name: `Delete ${customerTransactions.name}` }),
    )
    await userEvent.click(page.getByRole('button', { name: 'Delete dataset' }))

    await expect
      .element(screen.list.getByText('No datasets yet. Add one with the Add a dataset form.'))
      .toBeVisible()
    await expect.element(screen.datasetsHeading).toHaveFocus()
    await expectToast(`Deleted "${customerTransactions.name}"`)
    await expectNoA11yViolations()
  })

  it.each([
    [320, 720],
    [1024, 768],
  ])('keeps focus clear of three of the longest toasts at %i × %i', async (width, height) => {
    // Without motion the stack is laid out at once, so where it ends can be measured.
    await emulateMedia([{ name: 'prefers-reduced-motion', value: 'reduce' }])
    await page.viewport(width, height)
    onTestFinished(async () => {
      await page.viewport(414, 896)
    })
    const screen = await renderLoaded()
    for (const index of [1, 2, 3]) {
      toast.error(`Couldn't delete "${longestName(index)}"`, {
        closeButton: true,
        duration: Infinity,
        description: networkErrorMessage,
      })
    }
    await expect.element(page.getByText(`Couldn't delete "${longestName(3)}"`)).toBeVisible()

    screen.list
      .getByRole('button', { name: `Delete ${productInventory.name}` })
      .element()
      .focus()
    await userEvent.tab()

    const lastDelete = screen.list.getByRole('button', { name: `Delete ${employeeDirectory.name}` })
    await expect.element(lastDelete).toHaveFocus()
    const stackTop = Math.min(
      ...Array.from(
        document.querySelectorAll('[data-sonner-toast][data-visible="true"]'),
        (shown) => shown.getBoundingClientRect().top,
      ),
    )
    expect(lastDelete.element().getBoundingClientRect().bottom).toBeLessThan(stackTop)
    await expectNoA11yViolations()
  })
})
