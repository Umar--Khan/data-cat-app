import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { expectNoA11yViolations } from '@/test/a11y'
import {
  DatasetListEmpty,
  DatasetListLoadError,
  DatasetListRefreshError,
  DatasetListSkeleton,
} from './dataset-list-states'

describe('DatasetListSkeleton', () => {
  it('draws three cards hidden from assistive technology', async () => {
    const screen = await render(<DatasetListSkeleton />)
    const cards = screen.container.querySelectorAll('[aria-hidden="true"]')

    expect(cards).toHaveLength(3)
    for (const card of cards) expect(card.textContent).toBe('')
    expect(cards[0]?.getBoundingClientRect().height).toBeGreaterThan(0)
    await expectNoA11yViolations()
  })
})

describe('DatasetListEmpty', () => {
  it('points to the form', async () => {
    const screen = await render(<DatasetListEmpty />)

    await expect
      .element(screen.getByText('No datasets yet. Add one with the Add a dataset form.'))
      .toBeVisible()
    await expectNoA11yViolations()
  })
})

describe('DatasetListLoadError', () => {
  it('shows the message and a Try again button, with no live role', async () => {
    const onRetry = vi.fn()
    const screen = await render(
      <DatasetListLoadError message="The server hit an unexpected error." onRetry={onRetry} />,
    )

    await expect.element(screen.getByText("Couldn't load datasets")).toBeVisible()
    await expect.element(screen.getByText('The server hit an unexpected error.')).toBeVisible()
    await expect.element(screen.getByRole('alert')).not.toBeInTheDocument()
    await expect.element(screen.getByRole('status')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledOnce()
    await expectNoA11yViolations()
  })
})

describe('DatasetListRefreshError', () => {
  it('warns that the list is stale, with Try again and no live role', async () => {
    const onRetry = vi.fn()
    const screen = await render(<DatasetListRefreshError retrying={false} onRetry={onRetry} />)

    await expect
      .element(screen.getByText("Couldn't refresh. Showing the last loaded list."))
      .toBeVisible()
    await expect.element(screen.getByRole('alert')).not.toBeInTheDocument()
    await expect.element(screen.getByRole('status')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledOnce()
    await expectNoA11yViolations()
  })

  it('keeps Try again focusable but inert while the retry runs', async () => {
    const onRetry = vi.fn()
    const screen = await render(<DatasetListRefreshError retrying onRetry={onRetry} />)
    const button = screen.getByRole('button', { name: 'Try again' })

    await expect.element(button).toHaveAttribute('aria-disabled', 'true')
    await expect.element(button).not.toHaveAttribute('disabled')
    // Playwright treats aria-disabled as not actionable, so force sends the click regardless.
    await userEvent.click(button, { force: true })
    await expect.element(button).toHaveFocus()
    expect(onRetry).not.toHaveBeenCalled()
    await expectNoA11yViolations()
  })
})
