import { describe, expect, it, onTestFinished } from 'vitest'
import { page } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { expectNoA11yViolations } from '@/test/a11y'
import { TagList } from './tag-list'

describe('TagList', () => {
  it('lists the tags in order as a list named Tags', async () => {
    const screen = await render(<TagList tags={['finance', 'transactions', 'PII', 'daily']} />)
    const list = screen.getByRole('list', { name: 'Tags' })

    await expect.element(list).toBeVisible()
    expect(
      list
        .getByRole('listitem')
        .elements()
        .map((item) => item.textContent),
    ).toEqual(['finance', 'transactions', 'PII', 'daily'])
    await expectNoA11yViolations()
  })

  it('says "No tags" instead of rendering an empty list', async () => {
    const screen = await render(<TagList tags={[]} />)

    await expect.element(screen.getByText('No tags', { exact: true })).toBeVisible()
    await expect.element(screen.getByRole('list')).not.toBeInTheDocument()
    await expectNoA11yViolations()
  })

  it('wraps a long unbroken tag instead of scrolling sideways at 320 px', async () => {
    const { innerWidth, innerHeight } = window
    await page.viewport(320, 720)
    onTestFinished(async () => {
      await page.viewport(innerWidth, innerHeight)
    })
    const tag = 'customer_lifetime_value_'.repeat(4)
    const screen = await render(<TagList tags={['finance', tag]} />)
    const item = screen.getByText(tag, { exact: true })
    await expect.element(item).toBeVisible()

    expect(item.element().scrollWidth).toBeLessThanOrEqual(item.element().clientWidth)
    expect(document.documentElement.scrollWidth).toBeLessThanOrEqual(window.innerWidth)
    await expectNoA11yViolations()
  })
})
