/// <reference types="@vitest/browser-playwright" />
import { describe, expect, it, onTestFinished, vi } from 'vitest'
import { cdp, page, userEvent } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { expectNoA11yViolations } from '@/test/a11y'
import { Alert } from './alert'
import { Button } from './button'

const focusRing = {
  outlineStyle: 'solid',
  outlineWidth: '2px',
  outlineOffset: '2px',
  outlineColor: 'var(--color-focus)',
}

async function emulateMedia(features: { name: string; value: string }[]) {
  await cdp().send('Emulation.setEmulatedMedia', { features })
  onTestFinished(async () => {
    await cdp().send('Emulation.setEmulatedMedia', { features: [] })
  })
}

describe('Button', () => {
  it('renders every variant, size and the pending state with no axe violations', async () => {
    const screen = await render(
      <>
        <Button>Add dataset</Button>
        <Button variant="secondary">Try again</Button>
        <Button variant="danger">Delete dataset</Button>
        <Button variant="danger" size="sm">
          Delete
        </Button>
        <Button type="submit" pending>
          Saving and curating…
        </Button>
      </>,
    )

    for (const name of [
      'Add dataset',
      'Try again',
      'Delete dataset',
      'Delete',
      'Saving and curating…',
    ]) {
      await expect.element(screen.getByRole('button', { name, exact: true })).toBeVisible()
    }
    await expectNoA11yViolations()
  })

  it('meets the 40 px target at md and 32 px at sm', async () => {
    const screen = await render(
      <>
        <Button>Add dataset</Button>
        <Button size="sm">Delete</Button>
      </>,
    )

    const md = screen.getByRole('button', { name: 'Add dataset' }).element().getBoundingClientRect()
    const sm = screen.getByRole('button', { name: 'Delete' }).element().getBoundingClientRect()
    expect(md.height).toBe(40)
    expect(md.width).toBeGreaterThanOrEqual(40)
    expect(sm.height).toBe(32)
    expect(sm.width).toBeGreaterThanOrEqual(32)
    await expectNoA11yViolations()
  })

  it('does not submit its form unless it is a submit button', async () => {
    const onSubmit = vi.fn()
    const screen = await render(
      <form
        aria-label="Example"
        onSubmit={(event) => {
          event.preventDefault()
          onSubmit()
        }}
      >
        <Button variant="secondary">Try again</Button>
        <Button type="submit">Add dataset</Button>
      </form>,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(onSubmit).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Add dataset' }))
    expect(onSubmit).toHaveBeenCalledOnce()
    await expectNoA11yViolations()
  })

  it('activates with Enter and Space', async () => {
    const onClick = vi.fn()
    const screen = await render(<Button onClick={onClick}>Add dataset</Button>)

    await userEvent.tab()
    await expect.element(screen.getByRole('button', { name: 'Add dataset' })).toHaveFocus()
    await userEvent.keyboard('{Enter}')
    await userEvent.keyboard(' ')

    expect(onClick).toHaveBeenCalledTimes(2)
    await expectNoA11yViolations()
  })

  it('shows the focus ring on every variant, while pending, and on alert backgrounds', async () => {
    const screen = await render(
      <>
        <Button>Add dataset</Button>
        <Button variant="secondary">Cancel</Button>
        <Button variant="danger">Delete dataset</Button>
        <Button pending>Saving and curating…</Button>
        <Alert
          tone="danger"
          title="Couldn't load datasets"
          action={
            <Button variant="secondary" size="sm">
              Try again
            </Button>
          }
        />
        <Alert
          tone="warning"
          title="Couldn't refresh. Showing the last loaded list."
          action={
            <Button variant="secondary" size="sm">
              Refresh
            </Button>
          }
        />
      </>,
    )

    for (const name of [
      'Add dataset',
      'Cancel',
      'Delete dataset',
      'Saving and curating…',
      'Try again',
      'Refresh',
    ]) {
      await userEvent.tab()
      const button = screen.getByRole('button', { name })
      await expect.element(button).toHaveFocus()
      await expect.element(button).toHaveStyle(focusRing)
    }
    await expectNoA11yViolations()
  })

  describe('pending', () => {
    it('is aria-disabled rather than disabled and shows a hidden spinner', async () => {
      const screen = await render(<Button pending>Saving and curating…</Button>)
      const button = screen.getByRole('button', { name: 'Saving and curating…' })

      await expect.element(button).toHaveAttribute('aria-disabled', 'true')
      await expect.element(button).not.toHaveAttribute('disabled')
      await expect.element(button).toHaveAccessibleName('Saving and curating…')
      const spinner = button.element().querySelector('svg')
      expect(spinner).not.toBeNull()
      await expect.element(page.elementLocator(spinner as SVGElement)).toBeVisible()
      await expect
        .element(page.elementLocator(spinner as SVGElement))
        .toHaveAttribute('aria-hidden', 'true')
      await expectNoA11yViolations()
    })

    it('has no spinner and no aria-disabled when idle', async () => {
      const screen = await render(<Button>Add dataset</Button>)
      const button = screen.getByRole('button', { name: 'Add dataset' })

      await expect.element(button).not.toHaveAttribute('aria-disabled')
      expect(button.element().querySelector('svg')).toBeNull()
      await expectNoA11yViolations()
    })

    it('ignores click, Enter, Space and implicit submission, and keeps focus', async () => {
      const onClick = vi.fn()
      const onSubmit = vi.fn()
      const screen = await render(
        <form
          aria-label="Example"
          onSubmit={(event) => {
            event.preventDefault()
            onSubmit()
          }}
        >
          <label>
            Name
            <input name="name" />
          </label>
          <Button type="submit" pending onClick={onClick}>
            Saving and curating…
          </Button>
        </form>,
      )
      const button = screen.getByRole('button', { name: 'Saving and curating…' })

      // Playwright treats aria-disabled as not actionable, so force sends the click regardless.
      await userEvent.click(button, { force: true })
      await expect.element(button).toHaveFocus()
      await userEvent.keyboard('{Enter}')
      await userEvent.keyboard(' ')
      await expect.element(button).toHaveFocus()

      await userEvent.click(screen.getByRole('textbox', { name: 'Name' }))
      await userEvent.keyboard('{Enter}')

      expect(onClick).not.toHaveBeenCalled()
      expect(onSubmit).not.toHaveBeenCalled()
      await expectNoA11yViolations()
    })

    it('keeps focus when it settles and then activates again', async () => {
      const onClick = vi.fn()
      const screen = await render(
        <Button pending onClick={onClick}>
          Saving and curating…
        </Button>,
      )

      await userEvent.tab()
      await expect
        .element(screen.getByRole('button', { name: 'Saving and curating…' }))
        .toHaveFocus()

      await screen.rerender(<Button onClick={onClick}>Add dataset</Button>)
      const button = screen.getByRole('button', { name: 'Add dataset' })
      await expect.element(button).toHaveFocus()
      await userEvent.keyboard('{Enter}')

      expect(onClick).toHaveBeenCalledOnce()
      await expectNoA11yViolations()
    })
  })

  it('merges a caller className over its own classes', async () => {
    const screen = await render(<Button className="rounded-lg px-8">Add dataset</Button>)
    const button = screen.getByRole('button', { name: 'Add dataset' })

    await expect.element(button).toHaveClass('rounded-lg', 'px-8', 'bg-accent')
    await expect.element(button).not.toHaveClass('rounded-md')
    await expect.element(button).not.toHaveClass('px-4')
    await expectNoA11yViolations()
  })

  it('keeps a visible boundary in forced-colours mode', async () => {
    const screen = await render(
      <>
        <Button>Add dataset</Button>
        <Button variant="secondary">Try again</Button>
        <Button variant="danger">Delete dataset</Button>
      </>,
    )
    const primary = screen.getByRole('button', { name: 'Add dataset' })
    const secondary = screen.getByRole('button', { name: 'Try again' })
    const danger = screen.getByRole('button', { name: 'Delete dataset' })
    await expect.element(primary).toHaveClass('border', 'border-transparent')
    await expect.element(danger).toHaveClass('border', 'border-transparent')
    await expect.element(secondary).toHaveClass('border', 'border-border-input')
    await expectNoA11yViolations()

    await emulateMedia([{ name: 'forced-colors', value: 'active' }])

    for (const button of [primary, secondary, danger]) {
      await expect.element(button).toHaveStyle({ borderTopWidth: '1px' })
      await expect
        .poll(() => getComputedStyle(button.element()).borderTopColor)
        .not.toBe('rgba(0, 0, 0, 0)')
    }
  })

  it('transitions only its background in 150 ms, and not at all under reduced motion', async () => {
    const screen = await render(<Button>Add dataset</Button>)
    const button = screen.getByRole('button', { name: 'Add dataset' })

    await expect
      .element(button)
      .toHaveStyle({ transitionProperty: 'background-color', transitionDuration: '0.15s' })
    await expectNoA11yViolations()

    await emulateMedia([{ name: 'prefers-reduced-motion', value: 'reduce' }])
    await expect.element(button).toHaveStyle({ transitionDuration: '0s' })
  })
})
