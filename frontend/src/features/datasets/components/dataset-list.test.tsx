import { http, HttpResponse } from 'msw'
import { useId, useRef } from 'react'
import { toast } from 'sonner'
import { beforeEach, describe, expect, it } from 'vitest'
import { page, userEvent } from 'vitest/browser'
import { datasetKeys } from '@/features/datasets/api/query-keys'
import { unreadableResponseMessage } from '@/lib/api/api-error'
import type { Dataset } from '@/lib/api/schema.gen'
import { expectNoA11yViolations } from '@/test/a11y'
import { emulateMedia } from '@/test/emulate-media'
import { apiUrl } from '@/test/msw/handlers'
import { deleteFails, deleteNotFound, hold, listFails } from '@/test/msw/scenarios'
import { seedDatasets, store } from '@/test/msw/store'
import { apiRequests, worker } from '@/test/msw/worker'
import { renderWithProviders } from '@/test/render'
import { DatasetList } from './dataset-list'

const [customerTransactions, productInventory, employeeDirectory] = seedDatasets as [
  Dataset,
  Dataset,
  Dataset,
]

const dialogDescription = "It will be removed from the catalogue. This can't be undone."

/** The page's "Datasets" section, as the shell renders it around the list. */
function DatasetsSection() {
  const headingId = useId()
  const headingRef = useRef<HTMLHeadingElement>(null)
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId} ref={headingRef} tabIndex={-1}>
        Datasets
      </h2>
      <DatasetList headingRef={headingRef} />
    </section>
  )
}

async function renderList() {
  const screen = await renderWithProviders(<DatasetsSection />)
  const section = screen.getByRole('region', { name: 'Datasets', exact: true })
  return Object.assign(screen, {
    section,
    status: section.getByRole('status'),
    datasetsHeading: section.getByRole('heading', { level: 2, name: 'Datasets' }),
    rowHeading: (name: string) => section.getByRole('heading', { level: 3, name }),
    row: (name: string) => section.getByRole('article', { name }),
    deleteButton: (name: string) => section.getByRole('button', { name: `Delete ${name}` }),
    tryAgain: section.getByRole('button', { name: 'Try again' }),
    rowNames: () =>
      section
        .getByRole('heading', { level: 3 })
        .elements()
        .map((heading) => heading.textContent),
  })
}

async function renderLoaded() {
  const screen = await renderList()
  await expect.element(screen.row(customerTransactions.name)).toBeVisible()
  return screen
}

type ListScreen = Awaited<ReturnType<typeof renderList>>

async function openDeleteDialog(screen: ListScreen, name: string) {
  await userEvent.click(screen.deleteButton(name))
  const dialog = page.getByRole('alertdialog', { name: `Delete "${name}"?` })
  await expect.element(dialog).toBeVisible()
  return dialog
}

async function confirmDelete(screen: ListScreen, name: string) {
  const dialog = await openDeleteDialog(screen, name)
  await userEvent.click(dialog.getByRole('button', { name: 'Delete dataset' }))
  await expect.element(dialog).not.toBeInTheDocument()
}

function toastTitles() {
  return toast.getToasts().map((shown) => ('title' in shown ? shown.title : undefined))
}

describe('DatasetList', () => {
  it('announces loading and shows three hidden skeleton cards until the list arrives', async () => {
    const gate = hold('GET')
    const screen = await renderList()
    await gate.arrived

    await expect.element(screen.status).toHaveTextContent('Loading datasets…')
    expect(screen.section.element().querySelectorAll('div[aria-hidden="true"]')).toHaveLength(3)
    await expect.element(screen.section.getByRole('article')).not.toBeInTheDocument()
    await expectNoA11yViolations()

    gate.release()
    await expect.element(screen.row(customerTransactions.name)).toBeVisible()
    await expect.element(screen.status).toBeEmptyDOMElement()
    expect(screen.section.element().querySelectorAll('div[aria-hidden="true"]')).toHaveLength(0)
    await expectNoA11yViolations()
  })

  it('says how to add one when the catalogue is empty', async () => {
    store.reset([])
    const screen = await renderList()

    await expect
      .element(screen.section.getByText('No datasets yet. Add one with the Add a dataset form.'))
      .toBeVisible()
    await expect.element(screen.section.getByRole('article')).not.toBeInTheDocument()
    await expect.element(screen.status).toBeEmptyDOMElement()
    await expectNoA11yViolations()
  })

  it('lists the seeds as articles in list items, each marked as sample data', async () => {
    const screen = await renderLoaded()

    expect(screen.rowNames()).toEqual([
      'Customer Transactions',
      'Product Inventory',
      'Employee Directory',
    ])
    for (const { name, owner } of seedDatasets) {
      const row = screen.row(name)
      expect(row.element().parentElement?.tagName).toBe('LI')
      expect(row.element().parentElement?.parentElement?.tagName).toBe('UL')
      await expect.element(row.getByRole('definition')).toHaveTextContent(owner)
      await expect.element(row.getByText('Sample data', { exact: true })).toBeVisible()
      await expect.element(row.getByRole('list', { name: 'Tags' })).toBeVisible()
      await expect.element(screen.deleteButton(name)).toBeVisible()
    }
    await expect.element(screen.status).toBeEmptyDOMElement()
    await expectNoA11yViolations()
  })

  it('keeps the order the server sends, without sorting', async () => {
    store.reset([employeeDirectory, customerTransactions, productInventory])
    const screen = await renderList()

    await expect.element(screen.row(employeeDirectory.name)).toBeVisible()
    expect(screen.rowNames()).toEqual([
      'Employee Directory',
      'Customer Transactions',
      'Product Inventory',
    ])
    await expectNoA11yViolations()
  })

  it('reports a failed load, and Try again loads again until the API answers', async () => {
    const stop = listFails()
    const screen = await renderList()

    await expect.element(screen.status).toHaveTextContent("Couldn't load datasets")
    // The status region and the alert's title.
    expect(screen.section.getByText("Couldn't load datasets").elements()).toHaveLength(2)
    await expect
      .element(screen.section.getByText('The server hit an unexpected error.'))
      .toBeVisible()
    await expect.element(screen.section.getByRole('alert')).not.toBeInTheDocument()
    await expectNoA11yViolations()

    const retry = hold('GET')
    await userEvent.click(screen.tryAgain)
    await retry.arrived
    await expect.element(screen.status).toHaveTextContent('Loading datasets…')
    await expect.element(screen.tryAgain).not.toBeInTheDocument()
    expect(screen.section.element().querySelectorAll('div[aria-hidden="true"]')).toHaveLength(3)
    await expect.element(screen.datasetsHeading).toHaveFocus()
    await expectNoA11yViolations()
    retry.release()
    await expect.element(screen.status).toHaveTextContent("Couldn't load datasets")

    stop()
    await userEvent.click(screen.tryAgain)
    await expect.element(screen.row(customerTransactions.name)).toBeVisible()
    await expect.element(screen.status).toBeEmptyDOMElement()
    await expect.element(screen.section.getByText("Couldn't load datasets")).not.toBeInTheDocument()
    await expect.element(screen.datasetsHeading).toHaveFocus()
    await expectNoA11yViolations()
  })

  it("explains a list it could not read in words, not the parser's", async () => {
    // What a static host answers when the API base URL points at it instead.
    worker.use(
      http.get(apiUrl('/datasets'), () =>
        HttpResponse.html('<!doctype html><title>Data Catalogue</title><div id="root"></div>'),
      ),
    )
    const screen = await renderList()

    await expect.element(screen.status).toHaveTextContent("Couldn't load datasets")
    await expect.element(screen.section.getByText(unreadableResponseMessage)).toBeVisible()
    expect(screen.section.element().textContent).not.toContain('Unexpected token')
    await expect.element(screen.tryAgain).toBeVisible()
    await expectNoA11yViolations()
  })

  it('keeps the list when a refresh fails, with a warning and Try again', async () => {
    const screen = await renderLoaded()
    const stop = listFails()

    await screen.queryClient.refetchQueries({ queryKey: datasetKeys.list })

    const failed = "Couldn't refresh. Showing the last loaded list."
    // The status region comes first, then the alert's title.
    const warning = screen.section.getByText(failed).last()
    await expect.element(warning).toBeVisible()
    await expect.element(screen.status).toHaveTextContent(failed)
    expect(screen.section.getByText(failed).elements()).toHaveLength(2)
    expect(screen.rowNames()).toHaveLength(3)
    await expect.element(screen.section.getByRole('alert')).not.toBeInTheDocument()
    await expectNoA11yViolations()

    // Failing again announces again, because the region clears while the retry runs.
    const failedRetry = hold('GET')
    await userEvent.click(screen.tryAgain)
    await failedRetry.arrived
    await expect.element(screen.status).toBeEmptyDOMElement()
    await expect.element(screen.datasetsHeading).toHaveFocus()
    failedRetry.release()
    await expect.element(screen.status).toHaveTextContent(failed)

    stop()
    const retry = hold('GET')
    await userEvent.click(screen.tryAgain)
    await retry.arrived
    await expect.element(screen.tryAgain).toHaveAttribute('aria-disabled', 'true')
    await expect.element(screen.status).toBeEmptyDOMElement()
    await expect.element(screen.datasetsHeading).toHaveFocus()
    expect(screen.rowNames()).toHaveLength(3)
    await expectNoA11yViolations()

    retry.release()
    await expect.element(warning).not.toBeInTheDocument()
    await expect.element(screen.status).toBeEmptyDOMElement()
    expect(screen.rowNames()).toHaveLength(3)
    await expect.element(screen.datasetsHeading).toHaveFocus()
    await expectNoA11yViolations()
  })

  describe('delete', () => {
    // sonner fades toasts in, and axe fails text caught half-faded. Under reduced motion sonner drops
    // its transitions, so a toast is either transparent, which axe skips, or opaque and checked.
    beforeEach(async () => {
      await emulateMedia([{ name: 'prefers-reduced-motion', value: 'reduce' }])
    })

    it('asks for confirmation with Cancel focused, and sends nothing on Cancel or Esc', async () => {
      const screen = await renderLoaded()
      const opener = screen.deleteButton(productInventory.name)

      const dialog = await openDeleteDialog(screen, productInventory.name)
      await expect.element(dialog).toHaveAccessibleDescription(dialogDescription)
      expect(
        dialog
          .getByRole('button')
          .elements()
          .map((button) => button.textContent),
      ).toEqual(['Cancel', 'Delete dataset'])
      await expect.element(dialog.getByRole('button', { name: 'Cancel' })).toHaveFocus()
      await expectNoA11yViolations()

      await userEvent.click(dialog.getByRole('button', { name: 'Cancel' }))
      await expect.element(dialog).not.toBeInTheDocument()
      await expect.element(opener).toHaveFocus()

      await userEvent.keyboard('{Enter}')
      await expect.element(dialog).toBeVisible()
      await userEvent.keyboard('{Escape}')
      await expect.element(dialog).not.toBeInTheDocument()
      await expect.element(opener).toHaveFocus()

      expect(screen.rowNames()).toHaveLength(3)
      expect(apiRequests()).toEqual(['GET /datasets'])
      await expectNoA11yViolations()
    })

    it("removes the row at once and focuses the next row's heading once it has gone", async () => {
      const screen = await renderLoaded()
      const gate = hold('DELETE')
      const deletedRow = screen.row(customerTransactions.name).element()
      const headingFocus: { heading: string | null; rowConnected: boolean }[] = []
      screen.section.element().addEventListener('focusin', ({ target }) => {
        if (target instanceof HTMLHeadingElement) {
          headingFocus.push({ heading: target.textContent, rowConnected: deletedRow.isConnected })
        }
      })

      await confirmDelete(screen, customerTransactions.name)
      await gate.arrived

      await expect.element(screen.row(customerTransactions.name)).not.toBeInTheDocument()
      await expect.element(screen.rowHeading(productInventory.name)).toHaveFocus()
      expect(screen.rowNames()).toEqual(['Product Inventory', 'Employee Directory'])
      await expectNoA11yViolations()

      gate.release()
      await expect.poll(toastTitles).toEqual(['Deleted "Customer Transactions"'])
      await expect.element(page.getByText('Deleted "Customer Transactions"')).toBeVisible()
      expect(screen.rowNames()).toEqual(['Product Inventory', 'Employee Directory'])
      await expect.element(screen.rowHeading(productInventory.name)).toHaveFocus()
      expect(headingFocus).toEqual([{ heading: 'Product Inventory', rowConnected: false }])
      expect(apiRequests()).toEqual(['GET /datasets', 'DELETE /datasets/1'])
      await expectNoA11yViolations()
    })

    it("focuses the previous row's heading when the last row is deleted", async () => {
      const screen = await renderLoaded()

      await confirmDelete(screen, employeeDirectory.name)

      await expect.element(screen.row(employeeDirectory.name)).not.toBeInTheDocument()
      await expect.element(screen.rowHeading(productInventory.name)).toHaveFocus()
      await expect.poll(toastTitles).toEqual(['Deleted "Employee Directory"'])
      await expectNoA11yViolations()
    })

    it('focuses the Datasets heading when the only row is deleted', async () => {
      store.reset([customerTransactions])
      const screen = await renderLoaded()

      await confirmDelete(screen, customerTransactions.name)

      await expect.element(screen.datasetsHeading).toHaveFocus()
      await expect
        .element(screen.section.getByText('No datasets yet. Add one with the Add a dataset form.'))
        .toBeVisible()
      await expect.poll(toastTitles).toEqual(['Deleted "Customer Transactions"'])
      await expectNoA11yViolations()
    })

    it('brings the row back with an error toast when the delete fails', async () => {
      deleteFails(customerTransactions.id)
      const screen = await renderLoaded()
      const gate = hold('DELETE')

      await confirmDelete(screen, customerTransactions.name)
      await gate.arrived
      await expect.element(screen.row(customerTransactions.name)).not.toBeInTheDocument()

      gate.release()
      await expect.element(screen.row(customerTransactions.name)).toBeVisible()
      expect(screen.rowNames()).toEqual([
        'Customer Transactions',
        'Product Inventory',
        'Employee Directory',
      ])
      await expect.poll(toastTitles).toEqual(['Couldn\'t delete "Customer Transactions"'])
      await expect
        .element(page.getByText('The server hit an unexpected error.', { exact: true }))
        .toBeVisible()
      await expect.element(screen.rowHeading(productInventory.name)).toHaveFocus()
      await expectNoA11yViolations()
    })

    it('removes the row with an info toast when it was already deleted elsewhere', async () => {
      deleteNotFound(customerTransactions.id)
      const screen = await renderLoaded()

      await confirmDelete(screen, customerTransactions.name)

      await expect.poll(toastTitles).toEqual(['"Customer Transactions" was already removed'])
      await expect.element(screen.row(customerTransactions.name)).not.toBeInTheDocument()
      await expect.element(screen.rowHeading(productInventory.name)).toHaveFocus()
      await expectNoA11yViolations()
    })

    it('keeps two overlapping deletes to their own rows and outcomes', async () => {
      deleteFails(productInventory.id)
      const screen = await renderLoaded()
      const first = hold('DELETE')
      const second = hold('DELETE')

      await confirmDelete(screen, customerTransactions.name)
      await first.arrived
      await expect.element(screen.rowHeading(productInventory.name)).toHaveFocus()
      await confirmDelete(screen, productInventory.name)
      await second.arrived

      await expect.element(screen.rowHeading(employeeDirectory.name)).toHaveFocus()
      expect(screen.rowNames()).toEqual(['Employee Directory'])

      second.release()
      await expect.element(screen.row(productInventory.name)).toBeVisible()
      expect(screen.rowNames()).toEqual(['Product Inventory', 'Employee Directory'])

      first.release()
      await expect
        .poll(() => toastTitles().sort())
        .toEqual(['Couldn\'t delete "Product Inventory"', 'Deleted "Customer Transactions"'])
      expect(screen.rowNames()).toEqual(['Product Inventory', 'Employee Directory'])
      await expect.element(screen.rowHeading(employeeDirectory.name)).toHaveFocus()
      await expectNoA11yViolations()
    })

    it('moves focus to the Datasets heading, once, when a refresh removed the row while its dialog was open', async () => {
      const screen = await renderLoaded()
      const dialog = await openDeleteDialog(screen, customerTransactions.name)
      store.remove(customerTransactions.id)
      await screen.queryClient.refetchQueries({ queryKey: datasetKeys.list })
      await expect.element(screen.row(customerTransactions.name)).not.toBeInTheDocument()

      await userEvent.click(dialog.getByRole('button', { name: 'Delete dataset' }))

      await expect.poll(toastTitles).toEqual(['"Customer Transactions" was already removed'])
      await expect.element(screen.datasetsHeading).toHaveFocus()
      await userEvent.tab()
      const focused = screen.deleteButton(productInventory.name)
      await expect.element(focused).toHaveFocus()
      store.remove(employeeDirectory.id)
      await screen.queryClient.refetchQueries({ queryKey: datasetKeys.list })
      await expect.element(screen.row(employeeDirectory.name)).not.toBeInTheDocument()
      await expect.element(focused).toHaveFocus()
      await expectNoA11yViolations()
    })

    it('moves focus only once, so later list changes leave it where the user put it', async () => {
      const screen = await renderLoaded()

      await confirmDelete(screen, customerTransactions.name)
      await expect.element(screen.rowHeading(productInventory.name)).toHaveFocus()
      await expect.poll(toastTitles).toEqual(['Deleted "Customer Transactions"'])

      await userEvent.tab()
      const focused = screen.deleteButton(productInventory.name)
      await expect.element(focused).toHaveFocus()

      store.add(
        { name: 'Trade Confirmations', owner: 'Middle Office', description: 'Confirmed trades.' },
        {
          tags: ['trading'],
          summary: 'Confirmed trades.',
          curation: customerTransactions.curation,
        },
      )
      await screen.queryClient.refetchQueries({ queryKey: datasetKeys.list })
      await expect.element(screen.row('Trade Confirmations')).toBeVisible()
      await expect.element(focused).toHaveFocus()
      await expectNoA11yViolations()
    })
  })
})
