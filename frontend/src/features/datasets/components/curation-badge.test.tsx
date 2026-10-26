import { describe, expect, it } from 'vitest'
import { render } from 'vitest-browser-react'
import type { Curation } from '@/lib/api/schema.gen'
import { expectNoA11yViolations } from '@/test/a11y'
import { CurationBadge } from './curation-badge'

const failureDetail = 'The AI service could not be reached.'

describe('CurationBadge', () => {
  it.each<[string, Curation, { text: string; icon: string; tone: string }]>([
    [
      'completed by anthropic',
      { status: 'completed', provider: 'anthropic', detail: null },
      { text: 'Curated by Claude', icon: 'lucide-sparkles', tone: 'bg-accent-subtle' },
    ],
    [
      'completed by keyword',
      { status: 'completed', provider: 'keyword', detail: null },
      { text: 'Keyword curated', icon: 'lucide-tag', tone: 'bg-surface-muted' },
    ],
    [
      'completed by seed',
      { status: 'completed', provider: 'seed', detail: null },
      { text: 'Sample data', icon: 'lucide-database', tone: 'bg-surface-muted' },
    ],
    [
      'failed with anthropic',
      { status: 'failed', provider: 'anthropic', detail: failureDetail },
      { text: 'Curation failed', icon: 'lucide-triangle-alert', tone: 'bg-warning-subtle' },
    ],
    [
      'failed with keyword',
      { status: 'failed', provider: 'keyword', detail: failureDetail },
      { text: 'Curation failed', icon: 'lucide-triangle-alert', tone: 'bg-warning-subtle' },
    ],
  ])('labels %s with text and a hidden icon', async (_, curation, expected) => {
    const screen = await render(<CurationBadge curation={curation} />)
    const badge = screen.getByText(expected.text, { exact: true })

    await expect.element(badge).toBeVisible()
    await expect.element(badge).toHaveClass(expected.tone)
    const icon = badge.element().querySelector('svg')
    expect(icon?.classList.contains(expected.icon)).toBe(true)
    expect(icon?.getAttribute('aria-hidden')).toBe('true')
    await expectNoA11yViolations()
  })
})
