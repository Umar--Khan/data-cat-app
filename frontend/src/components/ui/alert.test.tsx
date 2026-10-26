import type { ComponentProps } from 'react'
import { describe, expect, expectTypeOf, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { expectNoA11yViolations } from '@/test/a11y'
import { Alert } from './alert'
import { Button } from './button'

describe('Alert', () => {
  it('shows a danger title, body and action without a live role', async () => {
    const onRetry = vi.fn()
    const screen = await render(
      <Alert
        tone="danger"
        title="Couldn't load datasets"
        action={
          <Button variant="secondary" size="sm" onClick={onRetry}>
            Try again
          </Button>
        }
      >
        Could not reach the server. Check your connection and try again.
      </Alert>,
    )

    await expect.element(screen.getByText("Couldn't load datasets")).toBeVisible()
    await expect
      .element(screen.getByText('Could not reach the server. Check your connection and try again.'))
      .toBeVisible()
    await expect.element(screen.getByRole('alert')).not.toBeInTheDocument()
    await expect.element(screen.getByRole('status')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onRetry).toHaveBeenCalledOnce()
    await expectNoA11yViolations()
  })

  it('shows a warning with a title alone', async () => {
    const screen = await render(
      <Alert tone="warning" title="Couldn't refresh. Showing the last loaded list." />,
    )
    const title = screen.getByText("Couldn't refresh. Showing the last loaded list.")

    await expect.element(title).toBeVisible()
    expect(title.element().nextElementSibling).toBeNull()
    await expectNoA11yViolations()
  })

  it('takes the alert role, the only live role it offers, when the caller asks for it', async () => {
    expectTypeOf<ComponentProps<typeof Alert>['role']>().toEqualTypeOf<'alert' | undefined>()
    const screen = await render(
      <Alert tone="danger" title="Couldn't add the dataset" role="alert">
        The server rejected the request.
      </Alert>,
    )

    await expect
      .element(screen.getByRole('alert'))
      .toHaveTextContent("Couldn't add the datasetThe server rejected the request.")
    await expectNoA11yViolations()
  })

  it('merges a caller className over its own classes', async () => {
    const screen = await render(
      <Alert tone="danger" title="Couldn't add the dataset" role="alert" className="p-3" />,
    )
    const alert = screen.getByRole('alert')

    await expect.element(alert).toHaveClass('p-3', 'bg-danger-subtle')
    await expect.element(alert).not.toHaveClass('p-4')
    await expectNoA11yViolations()
  })
})
