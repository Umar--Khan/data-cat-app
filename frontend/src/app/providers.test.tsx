import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { describe, expect, it, onTestFinished } from 'vitest'
import { page, userEvent } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { expectNoA11yViolations } from '@/test/a11y'
import { emulateMedia } from '@/test/emulate-media'
import { focusRing } from '@/test/focus-ring'
import { Providers, Toaster } from './providers'

const region = page.getByRole('region', { name: 'Notifications alt+T' })

function toastElement(title: string): HTMLElement {
  const element = page.getByText(title, { exact: true }).element().closest('[data-sonner-toast]')
  if (!(element instanceof HTMLElement)) throw new Error(`"${title}" is not in a toast`)
  return element
}

/** Waits for the toast to finish fading in: axe skips text that is transparent, not half-faded. */
async function shown(title: string): Promise<HTMLElement> {
  await expect.element(page.getByText(title, { exact: true })).toBeInTheDocument()
  const element = toastElement(title)
  await expect.poll(() => getComputedStyle(element).opacity).toBe('1')
  return element
}

/** A colour as the browser computes it, so token values compare with computed styles. */
function resolved(color: string): string {
  const probe = document.createElement('span')
  probe.style.color = color
  document.body.append(probe)
  const value = getComputedStyle(probe).color
  probe.remove()
  return value
}

async function viewport(width: number, height: number) {
  await page.viewport(width, height)
  onTestFinished(async () => {
    await page.viewport(414, 896)
  })
}

function wait(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

describe('Providers', () => {
  it('gives the app one query client for as long as it is mounted', async () => {
    const clients: QueryClient[] = []
    function Probe({ label }: { label: string }) {
      clients.push(useQueryClient())
      return <p>{label}</p>
    }
    const screen = await render(
      <Providers>
        <Probe label="first" />
      </Providers>,
    )
    await screen.rerender(
      <Providers>
        <Probe label="second" />
      </Providers>,
    )

    await expect.element(screen.getByText('second')).toBeVisible()
    expect(new Set(clients).size).toBe(1)
    expect(clients[0]?.getDefaultOptions().queries?.staleTime).toBe(30_000)
  })

  it('mounts the toaster', async () => {
    await render(<Providers>{null}</Providers>)
    toast.success('Added "Trade Confirmations"')

    await expect.element(region.getByText('Added "Trade Confirmations"')).toBeVisible()
    await shown('Added "Trade Confirmations"')
    await expectNoA11yViolations()
  })
})

describe('Toaster', () => {
  it('stacks toasts at the bottom right, three at a time', async () => {
    await viewport(1024, 768)
    await render(<Toaster />)
    for (const title of ['One', 'Two', 'Three', 'Four']) toast(title)
    const newest = await shown('Four')

    const list = newest.closest('[data-sonner-toaster]')
    expect(list).toHaveAttribute('data-y-position', 'bottom')
    expect(list).toHaveAttribute('data-x-position', 'right')
    const box = newest.getBoundingClientRect()
    expect(window.innerWidth - box.right).toBe(24)
    expect(window.innerHeight - box.bottom).toBe(24)
    expect(toastElement('One')).toHaveAttribute('data-visible', 'false')
    for (const title of ['Two', 'Three', 'Four']) {
      expect(toastElement(title)).toHaveAttribute('data-visible', 'true')
    }
    await expectNoA11yViolations()
  })

  it.each([
    ['success', 'var(--color-success-subtle)', 'var(--color-success-fg)'],
    ['info', 'var(--color-surface-muted)', 'var(--color-fg-muted)'],
    ['warning', 'var(--color-warning-subtle)', 'var(--color-warning-fg)'],
    ['error', 'var(--color-danger-subtle)', 'var(--color-danger)'],
  ] as const)('colours %s toasts with the tokens, at AA contrast', async (type, bg, fg) => {
    await render(<Toaster />)
    toast[type]('Title', { description: 'Description', closeButton: true })
    const shownToast = await shown('Title')

    expect(getComputedStyle(shownToast).backgroundColor).toBe(resolved(bg))
    expect(getComputedStyle(shownToast).color).toBe(resolved(fg))
    expect(getComputedStyle(page.getByText('Description').element()).color).toBe(
      resolved('var(--color-fg)'),
    )
    await expectNoA11yViolations()
  })

  it('gives a close button only to toasts that ask for one, at 24 × 24 px', async () => {
    await render(<Toaster />)
    toast.success('Brief')
    toast.error('Lingering', { closeButton: true })
    await shown('Lingering')

    expect(toastElement('Brief').querySelector('button')).toBeNull()
    // Layout size: the bounding box also carries the button's offset and the toast's transforms.
    const close = page.getByRole('button', { name: 'Close toast' }).element() as HTMLButtonElement
    expect([close.offsetWidth, close.offsetHeight]).toEqual([24, 24])
    await expectNoA11yViolations()
  })

  it('keeps the focus ring on toasts and their close buttons', async () => {
    await render(
      <>
        <button type="button">Before</button>
        <Toaster />
      </>,
    )
    toast.error('Lingering', { closeButton: true })
    const lingering = await shown('Lingering')
    await userEvent.click(page.getByRole('button', { name: 'Before' }))

    await userEvent.tab()
    expect(document.activeElement).toBe(lingering)
    expect(getComputedStyle(lingering)).toMatchObject({
      ...focusRing,
      outlineColor: resolved(focusRing.outlineColor),
    })
    await userEvent.tab()
    await expect.element(page.getByRole('button', { name: 'Close toast' })).toHaveFocus()
    expect(
      getComputedStyle(page.getByRole('button', { name: 'Close toast' }).element()),
    ).toMatchObject({ ...focusRing, outlineColor: resolved(focusRing.outlineColor) })
    await expectNoA11yViolations()
  })

  // The timer tests hover or focus a toast that never expires before the timed toasts arrive, so
  // they cannot lose a race with a 500 ms timer however slowly the pointer or Tab lands.

  it('pauses toasts while the pointer is over them', async () => {
    // Hovering waits for the toast to stop moving.
    await emulateMedia([{ name: 'prefers-reduced-motion', value: 'reduce' }])
    await render(<Toaster />)
    toast('Anchor', { duration: Infinity })
    await shown('Anchor')
    await userEvent.hover(page.getByText('Anchor'))
    toast('Hovered', { duration: 500 })
    await expect.element(page.getByText('Hovered')).toBeInTheDocument()

    await wait(800)
    await expect.element(page.getByText('Hovered')).toBeInTheDocument()
    await expectNoA11yViolations()

    await userEvent.unhover(page.getByText('Anchor'))
    await expect.element(page.getByText('Hovered')).not.toBeInTheDocument()
  })

  it('pauses toasts and lays the stack out while focus is inside it', async () => {
    await render(
      <>
        <button type="button">Before</button>
        <Toaster />
      </>,
    )
    toast('Anchor', { duration: Infinity })
    const anchor = await shown('Anchor')
    await userEvent.click(page.getByRole('button', { name: 'Before' }))

    await userEvent.tab()
    expect(document.activeElement).toBe(anchor)
    await expect.element(anchor).toHaveAttribute('data-expanded', 'true')
    toast('Older', { duration: 500 })
    toast('Newer', { duration: 500 })
    await expect.element(page.getByText('Newer')).toBeInTheDocument()
    await wait(800)
    await expect.element(page.getByText('Newer')).toBeInTheDocument()
    await expect.element(page.getByText('Older')).toBeInTheDocument()
    await expectNoA11yViolations()

    // sonner renders the newest toast first, so Shift+Tab from the anchor would stay in the stack.
    await userEvent.click(page.getByRole('button', { name: 'Before' }))
    await expect.element(page.getByText('Newer')).not.toBeInTheDocument()
    await expect.element(page.getByText('Older')).not.toBeInTheDocument()
  })

  it('keeps the stack expanded when focus leaves it while the pointer is still over it', async () => {
    // Hovering waits for the toast to stop moving.
    await emulateMedia([{ name: 'prefers-reduced-motion', value: 'reduce' }])
    await render(
      <>
        <button type="button">Before</button>
        <Toaster />
      </>,
    )
    toast('Hovered')
    const hovered = await shown('Hovered')
    page.getByRole('button', { name: 'Before' }).element().focus()
    await userEvent.hover(page.getByText('Hovered'))

    await userEvent.tab()
    expect(document.activeElement).toBe(hovered)
    await userEvent.tab({ shift: true })

    await expect.element(page.getByRole('button', { name: 'Before' })).toHaveFocus()
    await expect.element(hovered).toHaveAttribute('data-expanded', 'true')
    await expectNoA11yViolations()
  })

  it('copies the front toast height onto the page while a toast shows', async () => {
    const height = () => document.documentElement.style.getPropertyValue('--front-toast-height')
    await render(<Toaster />)
    toast('Measured')
    const list = (await shown('Measured')).closest<HTMLElement>('[data-sonner-toaster]')

    await expect.poll(height).toMatch(/^[1-9][\d.]*px$/)
    expect(height()).toBe(list?.style.getPropertyValue('--front-toast-height'))

    toast.dismiss()
    await expect.poll(height).toBe('')
  })

  it('moves focus to the notifications on Alt+T, with the ring on their toasts', async () => {
    await render(<Toaster />)
    toast('Reachable')
    const reachable = await shown('Reachable')

    await userEvent.keyboard('{Alt>}t{/Alt}')
    expect(document.activeElement).toBe(reachable.closest('[data-sonner-toaster]'))
    expect(region.element().contains(document.activeElement)).toBe(true)
    // The focused list has no height of its own to draw a ring around.
    expect(getComputedStyle(reachable)).toMatchObject({
      ...focusRing,
      outlineColor: resolved(focusRing.outlineColor),
    })
    await expectNoA11yViolations()
  })
})
