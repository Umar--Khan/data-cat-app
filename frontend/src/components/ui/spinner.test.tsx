/// <reference types="@vitest/browser-playwright" />
import { describe, expect, it, onTestFinished } from 'vitest'
import { cdp, page } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { expectNoA11yViolations } from '@/test/a11y'
import { Spinner } from './spinner'

async function emulateMedia(features: { name: string; value: string }[]) {
  await cdp().send('Emulation.setEmulatedMedia', { features })
  onTestFinished(async () => {
    await cdp().send('Emulation.setEmulatedMedia', { features: [] })
  })
}

async function renderSpinner(className?: string) {
  const screen = await render(<Spinner className={className} />)
  const svg = screen.container.querySelector('svg')
  expect(svg).not.toBeNull()
  return page.elementLocator(svg as SVGElement)
}

describe('Spinner', () => {
  it('is hidden from assistive technology', async () => {
    const spinner = await renderSpinner()

    await expect.element(spinner).toBeVisible()
    await expect.element(spinner).toHaveAttribute('aria-hidden', 'true')
    await expectNoA11yViolations()
  })

  it('spins, and stays still under reduced motion', async () => {
    const spinner = await renderSpinner()

    await expect.element(spinner).toHaveStyle({ animationName: 'spin' })
    await expectNoA11yViolations()

    await emulateMedia([{ name: 'prefers-reduced-motion', value: 'reduce' }])
    await expect.element(spinner).toHaveStyle({ animationName: 'none' })
  })

  it('merges a caller className over its size', async () => {
    const spinner = await renderSpinner('size-5')

    await expect.element(spinner).toHaveClass('size-5')
    await expect.element(spinner).not.toHaveClass('size-4')
    await expect.element(spinner).toHaveStyle({ width: '20px', height: '20px' })
    await expectNoA11yViolations()
  })
})
