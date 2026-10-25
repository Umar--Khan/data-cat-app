import axe from 'axe-core'
import { expect } from 'vitest'

const wcag22aa = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

export async function expectNoA11yViolations(context: Element = document.body) {
  const { violations } = await axe.run(context, { runOnly: { type: 'tag', values: wcag22aa } })
  expect(
    violations.map(({ id, nodes }) => ({
      id,
      targets: nodes.map(({ target }) => target.join(' ')),
    })),
  ).toEqual([])
}
