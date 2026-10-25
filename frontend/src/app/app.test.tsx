import { describe, expect, it } from 'vitest'
import { userEvent } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { expectNoA11yViolations } from '@/test/a11y'
import { App } from './app'

describe('App', () => {
  it('shows the page heading and both sections', async () => {
    const screen = await render(<App />)

    await expect
      .element(screen.getByRole('heading', { level: 1, name: 'Data Catalogue' }))
      .toBeVisible()
    await expect
      .element(screen.getByRole('region', { name: 'Add a dataset', exact: true }))
      .toContainElement(screen.getByRole('heading', { level: 2, name: 'Add a dataset' }).element())
    await expect
      .element(screen.getByRole('region', { name: 'Datasets', exact: true }))
      .toContainElement(screen.getByRole('heading', { level: 2, name: 'Datasets' }).element())
  })

  it('moves focus to the Datasets heading through the skip link', async () => {
    const screen = await render(<App />)
    const skipLink = screen.getByRole('link', { name: 'Skip to datasets' })

    await userEvent.tab()
    await expect.element(skipLink).toHaveFocus()
    await expect.element(skipLink).toBeVisible()

    await userEvent.keyboard('{Enter}')
    await expect.element(screen.getByRole('heading', { level: 2, name: 'Datasets' })).toHaveFocus()
  })

  it('has no WCAG 2.2 A or AA violations', async () => {
    await render(<App />)

    await expectNoA11yViolations()
  })
})
