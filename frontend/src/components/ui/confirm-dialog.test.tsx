import { StrictMode, useRef, useState } from 'react'
import { describe, expect, it, onTestFinished, vi } from 'vitest'
import { page, userEvent } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { expectNoA11yViolations } from '@/test/a11y'
import { focusRing } from '@/test/focus-ring'
import { Button } from './button'
import { ConfirmDialog } from './confirm-dialog'

const title = 'Delete "Sales"?'
const description = "It will be removed from the catalogue. This can't be undone."

function DeleteRow({ onConfirm = () => undefined }: { onConfirm?: () => void }) {
  const [open, setOpen] = useState(false)
  const nextHeadingRef = useRef<HTMLHeadingElement>(null)
  return (
    <>
      <Button
        variant="danger"
        size="sm"
        aria-label="Delete Sales"
        onClick={() => {
          setOpen(true)
        }}
      >
        Delete
      </Button>
      <h3 ref={nextHeadingRef} tabIndex={-1}>
        Inventory
      </h3>
      <ConfirmDialog
        open={open}
        title={title}
        description={description}
        confirmLabel="Delete dataset"
        onClose={() => {
          setOpen(false)
        }}
        onConfirm={() => {
          onConfirm()
          nextHeadingRef.current?.focus()
        }}
      />
    </>
  )
}

async function openDialog() {
  const onConfirm = vi.fn()
  const screen = await render(<DeleteRow onConfirm={onConfirm} />)
  const opener = screen.getByRole('button', { name: 'Delete Sales' })
  await userEvent.click(opener)
  const dialog = screen.getByRole('alertdialog', { name: title })
  await expect.element(dialog).toBeVisible()
  return { screen, opener, dialog, onConfirm }
}

describe('ConfirmDialog', () => {
  it('is closed until opened', async () => {
    const screen = await render(<DeleteRow />)

    await expect.element(screen.getByRole('alertdialog')).not.toBeInTheDocument()
    await expectNoA11yViolations()
  })

  it('opens as a modal alert dialog with Cancel first and focused', async () => {
    const { dialog } = await openDialog()

    await expect.element(dialog).toHaveAccessibleDescription(description)
    expect(
      dialog
        .getByRole('button')
        .elements()
        .map((button) => button.textContent),
    ).toEqual(['Cancel', 'Delete dataset'])
    await expect.element(dialog.getByRole('button', { name: 'Cancel' })).toHaveFocus()
    await expectNoA11yViolations()
  })

  it('closes on Esc and returns focus to the opener', async () => {
    const { opener, dialog, onConfirm } = await openDialog()

    await userEvent.keyboard('{Escape}')

    await expect.element(dialog).not.toBeInTheDocument()
    await expect.element(opener).toHaveFocus()
    expect(onConfirm).not.toHaveBeenCalled()
    await expectNoA11yViolations()
  })

  it('closes on Cancel by Space or Enter and returns focus to the opener', async () => {
    const { screen, opener, dialog, onConfirm } = await openDialog()

    await userEvent.keyboard(' ')
    await expect.element(dialog).not.toBeInTheDocument()
    await expect.element(opener).toHaveFocus()

    await userEvent.keyboard('{Enter}')
    await expect.element(screen.getByRole('alertdialog', { name: title })).toBeVisible()
    await userEvent.keyboard('{Enter}')
    await expect.element(dialog).not.toBeInTheDocument()
    await expect.element(opener).toHaveFocus()

    expect(onConfirm).not.toHaveBeenCalled()
    await expectNoA11yViolations()
  })

  it('confirms, closes, and leaves focus where the caller puts it', async () => {
    const { screen, dialog, onConfirm } = await openDialog()

    await userEvent.tab()
    await expect.element(dialog.getByRole('button', { name: 'Delete dataset' })).toHaveFocus()
    await userEvent.keyboard('{Enter}')

    expect(onConfirm).toHaveBeenCalledOnce()
    await expect.element(dialog).not.toBeInTheDocument()
    await expect.element(screen.getByRole('heading', { name: 'Inventory' })).toHaveFocus()
    await expectNoA11yViolations()
  })

  it('shows the focus ring on both buttons when opened from the keyboard', async () => {
    const screen = await render(<DeleteRow />)

    await userEvent.tab()
    await userEvent.keyboard('{Enter}')
    const dialog = screen.getByRole('alertdialog', { name: title })
    const cancel = dialog.getByRole('button', { name: 'Cancel' })
    await expect.element(cancel).toHaveFocus()
    await expect.element(cancel).toHaveStyle(focusRing)

    await userEvent.tab()
    const confirm = dialog.getByRole('button', { name: 'Delete dataset' })
    await expect.element(confirm).toHaveFocus()
    await expect.element(confirm).toHaveStyle(focusRing)
    await expectNoA11yViolations()
  })

  it('wraps a long unbroken name instead of scrolling sideways at 320 px', async () => {
    const { innerWidth, innerHeight } = window
    await page.viewport(320, 720)
    onTestFinished(async () => {
      await page.viewport(innerWidth, innerHeight)
    })
    const name = 'customer_lifetime_value_'.repeat(5)
    const longTitle = `Delete "${name}"?`
    const screen = await render(
      <ConfirmDialog
        open
        title={longTitle}
        description={`${name} will be removed from the catalogue.`}
        confirmLabel="Delete dataset"
        onClose={() => undefined}
        onConfirm={() => undefined}
      />,
    )
    const dialog = screen.getByRole('alertdialog', { name: longTitle })
    await expect.element(dialog).toBeVisible()

    for (const element of [
      dialog.element(),
      dialog.getByRole('heading').element(),
      dialog.getByText(/will be removed/).element(),
    ]) {
      expect(element.scrollWidth).toBeLessThanOrEqual(element.clientWidth)
    }
    await expectNoA11yViolations()
  })

  it('can be opened again before the close event arrives', async () => {
    const { opener, dialog } = await openDialog()
    const element = dialog.element() as HTMLDialogElement
    const cancel = dialog.getByRole('button', { name: 'Cancel' }).element() as HTMLButtonElement
    // Two inputs a microtask apart, as separate key presses are: React renders in between, but the
    // close event the first click queues is a task, so it arrives only after the second click.
    cancel.click()
    await Promise.resolve()
    ;(opener.element() as HTMLButtonElement).click()
    await new Promise((resolve) => setTimeout(resolve))

    expect(element.open).toBe(true)
    await expect.element(dialog).toBeVisible()
  })

  it('reports a close it did not make, so it can be opened again', async () => {
    const { opener, dialog } = await openDialog()
    // As when the browser handles Esc without a cancel event: only the close event follows.
    ;(dialog.element() as HTMLDialogElement).close()
    await expect.element(dialog).not.toBeInTheDocument()

    await userEvent.click(opener)
    await expect.element(dialog).toBeVisible()
  })

  it('opens and closes with the open prop, reporting no close it was told to make', async () => {
    const onClose = vi.fn()
    const props = {
      title,
      description,
      confirmLabel: 'Delete dataset',
      onClose,
      onConfirm: () => undefined,
    }
    const screen = await render(
      <StrictMode>
        <ConfirmDialog open {...props} />
      </StrictMode>,
    )
    await expect.element(screen.getByRole('alertdialog', { name: title })).toBeVisible()
    await expectNoA11yViolations()

    await screen.rerender(
      <StrictMode>
        <ConfirmDialog open={false} {...props} />
      </StrictMode>,
    )

    await expect.element(screen.getByRole('alertdialog')).not.toBeInTheDocument()
    await new Promise((resolve) => setTimeout(resolve))
    expect(onClose).not.toHaveBeenCalled()
  })

  it('merges a caller className over its own classes', async () => {
    const screen = await render(
      <ConfirmDialog
        open
        title={title}
        description={description}
        confirmLabel="Delete dataset"
        onClose={() => undefined}
        onConfirm={() => undefined}
        className="max-w-lg"
      />,
    )
    const dialog = screen.getByRole('alertdialog', { name: title })

    await expect.element(dialog).toHaveClass('max-w-lg', 'bg-surface')
    await expect.element(dialog).not.toHaveClass('max-w-md')
    await expectNoA11yViolations()
  })
})
