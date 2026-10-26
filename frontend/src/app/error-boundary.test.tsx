import { describe, expect, it, onTestFinished, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { reloadPage } from '@/app/reload-page'
import { expectNoA11yViolations } from '@/test/a11y'
import { ErrorBoundary } from './error-boundary'

// A real reload would take the test page with it.
vi.mock('@/app/reload-page', () => ({ reloadPage: vi.fn() }))

const renderError = new Error('A component failed to render')

function Thrower(): never {
  throw renderError
}

describe('ErrorBoundary', () => {
  it('renders its children while nothing fails', async () => {
    const screen = await render(
      <ErrorBoundary>
        <p>The page</p>
      </ErrorBoundary>,
    )

    await expect.element(screen.getByText('The page')).toBeVisible()
  })

  it('replaces a failed render with a focused fallback that reloads the page', async () => {
    // React reports what a boundary catches through console.error; silenced here and asserted.
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    onTestFinished(() => {
      consoleError.mockRestore()
    })
    const screen = await render(
      <ErrorBoundary>
        <p>The page</p>
        <Thrower />
      </ErrorBoundary>,
    )

    const heading = screen.getByRole('heading', { level: 1, name: 'Something went wrong' })
    await expect.element(heading).toHaveFocus()
    await expect.element(screen.getByRole('main')).toContainElement(heading.element())
    await expect
      .element(
        screen.getByText(
          'The page hit an unexpected error. Reload it to carry on; saved datasets are not affected.',
        ),
      )
      .toBeVisible()
    await expect.element(screen.getByText('The page')).not.toBeInTheDocument()
    expect(consoleError.mock.calls.flat()).toContain(renderError)
    await expectNoA11yViolations()

    await userEvent.click(screen.getByRole('button', { name: 'Reload page' }))
    expect(reloadPage).toHaveBeenCalledOnce()
  })
})
