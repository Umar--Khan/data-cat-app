import { Database, Sparkles, TriangleAlert } from 'lucide-react'
import { describe, expect, it } from 'vitest'
import { page } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { expectNoA11yViolations } from '@/test/a11y'
import { emulateMedia } from '@/test/emulate-media'
import { Badge } from './badge'

describe('Badge', () => {
  it('renders every tone with its text and a hidden icon, with no axe violations', async () => {
    const screen = await render(
      <>
        <Badge tone="accent" icon={Sparkles}>
          Curated by Claude
        </Badge>
        <Badge tone="neutral" icon={Database}>
          Sample data
        </Badge>
        <Badge tone="warning" icon={TriangleAlert}>
          Curation failed
        </Badge>
      </>,
    )

    for (const text of ['Curated by Claude', 'Sample data', 'Curation failed']) {
      const badge = screen.getByText(text, { exact: true })
      await expect.element(badge).toBeVisible()
      const icon = badge.element().querySelector('svg')
      expect(icon).not.toBeNull()
      await expect
        .element(page.elementLocator(icon as SVGElement))
        .toHaveAttribute('aria-hidden', 'true')
    }
    await expectNoA11yViolations()
  })

  it('defaults to the neutral tone and renders text alone without an icon', async () => {
    const screen = await render(<Badge>Keyword curated</Badge>)
    const badge = screen.getByText('Keyword curated', { exact: true })

    await expect.element(badge).toHaveClass('bg-surface-muted', 'text-fg-muted')
    expect(badge.element().querySelector('svg')).toBeNull()
    await expectNoA11yViolations()
  })

  it('merges a caller className over its own classes', async () => {
    const screen = await render(
      <Badge tone="accent" className="px-2">
        Curated by Claude
      </Badge>,
    )
    const badge = screen.getByText('Curated by Claude', { exact: true })

    await expect.element(badge).toHaveClass('px-2', 'bg-accent-subtle')
    await expect.element(badge).not.toHaveClass('px-1.5')
    await expectNoA11yViolations()
  })

  it('keeps a visible boundary in forced-colours mode', async () => {
    const screen = await render(<Badge tone="warning">Curation failed</Badge>)
    const badge = screen.getByText('Curation failed', { exact: true })
    await expect.element(badge).toHaveClass('border', 'border-transparent')
    await expectNoA11yViolations()

    await emulateMedia([{ name: 'forced-colors', value: 'active' }])

    await expect.element(badge).toHaveStyle({ borderTopWidth: '1px' })
    await expect
      .poll(() => getComputedStyle(badge.element()).borderTopColor)
      .not.toBe('rgba(0, 0, 0, 0)')
  })
})
