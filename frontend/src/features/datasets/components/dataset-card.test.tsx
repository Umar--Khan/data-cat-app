import { createRef } from 'react'
import { describe, expect, it, onTestFinished, vi } from 'vitest'
import { page, userEvent } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import type { Dataset } from '@/lib/api/schema.gen'
import { expectNoA11yViolations } from '@/test/a11y'
import { failedCuration, seedDatasets } from '@/test/msw/store'
import { DatasetCard } from './dataset-card'

const [customerTransactions] = seedDatasets as [Dataset, ...Dataset[]]

const savedWithoutCuration: Dataset = {
  id: '4',
  name: 'Trade Confirmations',
  owner: 'Middle Office',
  description: 'Daily export of confirmed trades.',
  ...failedCuration,
  createdAt: '2026-10-26T09:00:00Z',
}

async function renderCard(dataset: Dataset) {
  const headingRef = createRef<HTMLHeadingElement>()
  const onDelete = vi.fn()
  const screen = await render(
    <DatasetCard dataset={dataset} headingRef={headingRef} onDelete={onDelete} />,
  )
  const article = screen.getByRole('article', { name: dataset.name })
  await expect.element(article).toBeVisible()
  return { screen, article, headingRef, onDelete }
}

describe('DatasetCard', () => {
  it('shows the name, owner, badge, tags and summary of a curated dataset', async () => {
    const { article, headingRef } = await renderCard(customerTransactions)

    const heading = article.getByRole('heading', { level: 3, name: 'Customer Transactions' })
    await expect.element(heading).toHaveAttribute('tabindex', '-1')
    expect(headingRef.current).toBe(heading.element())
    await expect.element(article.getByRole('term')).toHaveTextContent('Owner')
    await expect.element(article.getByRole('definition')).toHaveTextContent('Finance Team')
    await expect.element(article.getByText('Sample data', { exact: true })).toBeVisible()
    expect(
      article
        .getByRole('list', { name: 'Tags' })
        .getByRole('listitem')
        .elements()
        .map((item) => item.textContent),
    ).toEqual(['finance', 'transactions', 'PII', 'daily'])
    await expect
      .element(article.getByText(/^A daily feed of customer transaction records/))
      .toBeVisible()
    await expectNoA11yViolations()
  })

  it('shows why curation failed in place of the summary, and no tags', async () => {
    const { article } = await renderCard(savedWithoutCuration)

    await expect.element(article.getByText('Curation failed', { exact: true })).toBeVisible()
    await expect
      .element(article.getByText('The AI service could not be reached.', { exact: true }))
      .toBeVisible()
    await expect.element(article.getByText('No tags', { exact: true })).toBeVisible()
    await expect.element(article.getByRole('list')).not.toBeInTheDocument()
    await expectNoA11yViolations()
  })

  it('has a 32 px Delete button that names its dataset and reports the click', async () => {
    const { article, onDelete } = await renderCard(customerTransactions)
    const button = article.getByRole('button', { name: 'Delete Customer Transactions' })

    // The name beyond "Delete" is visually hidden, so the visible label starts the accessible name.
    const hidden = button.getByText('Customer Transactions')
    await expect.element(hidden).toHaveStyle({ position: 'absolute', width: '1px', height: '1px' })
    expect(hidden.element().previousSibling?.textContent).toBe('Delete')
    expect(button.element().getBoundingClientRect().height).toBeGreaterThanOrEqual(32)

    await userEvent.click(button)
    expect(onDelete).toHaveBeenCalledOnce()
    await expectNoA11yViolations()
  })

  it('wraps a long unbroken name, owner and tag instead of scrolling sideways at 320 px', async () => {
    const { innerWidth, innerHeight } = window
    await page.viewport(320, 720)
    onTestFinished(async () => {
      await page.viewport(innerWidth, innerHeight)
    })
    const long = 'customer_lifetime_value_'.repeat(5)
    const { article } = await renderCard({
      ...customerTransactions,
      name: long,
      owner: `${long}team`,
      tags: [`${long}tag`],
      summary: `${long}summary`,
    })

    for (const element of [
      article.element(),
      article.getByRole('heading').element(),
      article.getByRole('definition').element(),
      article.getByRole('listitem').element(),
      article.getByText(`${long}summary`).element(),
    ]) {
      expect(element.scrollWidth).toBeLessThanOrEqual(element.clientWidth)
    }
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(window.innerWidth)
    await expectNoA11yViolations()
  })
})
