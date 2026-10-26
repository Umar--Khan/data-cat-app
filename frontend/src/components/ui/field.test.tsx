import { createRef } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { expectNoA11yViolations } from '@/test/a11y'
import { TextareaField, TextField } from './field'

const hint = 'What the data contains and how often it updates. Used to generate tags and a summary.'
const focusRing = {
  outlineStyle: 'solid',
  outlineWidth: '2px',
  outlineOffset: '2px',
  outlineColor: 'var(--color-focus)',
}

describe('TextField', () => {
  it('labels the input and passes native attributes through', async () => {
    const screen = await render(<TextField label="Name" name="name" required autoComplete="off" />)
    const input = screen.getByRole('textbox', { name: 'Name' })

    await expect.element(input).toBeVisible()
    await expect.element(input).toBeRequired()
    await expect.element(input).toHaveAttribute('name', 'name')
    await expect.element(input).toHaveAttribute('autocomplete', 'off')
    await expect.element(input).not.toHaveAttribute('placeholder')
    await expect.element(input).not.toHaveAttribute('aria-invalid')
    await expect.element(input).not.toHaveAttribute('aria-describedby')
    await expectNoA11yViolations()
  })

  it('describes the input with its hint', async () => {
    const screen = await render(<TextField label="Owner" hint="The team that maintains it." />)
    const input = screen.getByRole('textbox', { name: 'Owner' })

    await expect.element(screen.getByText('The team that maintains it.')).toBeVisible()
    await expect.element(input).toHaveAccessibleDescription('The team that maintains it.')
    await expect.element(input).not.toHaveAttribute('aria-invalid')
    await expectNoA11yViolations()
  })

  it('marks an error invalid and describes it after the hint', async () => {
    const screen = await render(
      <TextField label="Owner" hint="The team that maintains it." error="Enter an owner" />,
    )
    const input = screen.getByRole('textbox', { name: 'Owner' })

    await expect.element(screen.getByText('Enter an owner')).toBeVisible()
    await expect.element(input).toHaveAttribute('aria-invalid', 'true')
    await expect
      .element(input)
      .toHaveAccessibleDescription('The team that maintains it. Enter an owner')
    await expectNoA11yViolations()
  })

  it('describes an error on its own when there is no hint', async () => {
    const screen = await render(<TextField label="Name" error="Enter a name" />)
    const input = screen.getByRole('textbox', { name: 'Name' })

    await expect.element(input).toHaveAttribute('aria-invalid', 'true')
    await expect.element(input).toHaveAccessibleDescription('Enter a name')
    await expectNoA11yViolations()
  })

  it('shows the focus ring when tabbed to, valid or invalid', async () => {
    const screen = await render(
      <>
        <TextField label="Name" />
        <TextField label="Owner" error="Enter an owner" />
      </>,
    )

    for (const name of ['Name', 'Owner']) {
      await userEvent.tab()
      const input = screen.getByRole('textbox', { name })
      await expect.element(input).toHaveFocus()
      await expect.element(input).toHaveStyle(focusRing)
    }
    await expectNoA11yViolations()
  })

  it('clears aria-invalid once the error is gone', async () => {
    const screen = await render(<TextField label="Name" error="Enter a name" />)
    await screen.rerender(<TextField label="Name" />)
    const input = screen.getByRole('textbox', { name: 'Name' })

    await expect.element(input).not.toHaveAttribute('aria-invalid')
    await expect.element(input).not.toHaveAttribute('aria-describedby')
    await expect.element(screen.getByText('Enter a name')).not.toBeInTheDocument()
    await expectNoA11yViolations()
  })

  it('takes a ref as a prop and reports changes', async () => {
    const ref = createRef<HTMLInputElement>()
    const onChange = vi.fn()
    const screen = await render(<TextField label="Name" ref={ref} onChange={onChange} />)
    const input = screen.getByRole('textbox', { name: 'Name' })

    ref.current?.focus()
    await expect.element(input).toHaveFocus()
    await userEvent.keyboard('Sales')

    await expect.element(input).toHaveValue('Sales')
    expect(onChange).toHaveBeenCalledTimes(5)
    await expectNoA11yViolations()
  })

  it('is read-only on request and keeps its value', async () => {
    const screen = await render(<TextField label="Name" defaultValue="Sales" readOnly />)
    const input = screen.getByRole('textbox', { name: 'Name' })

    await expect.element(input).toHaveAttribute('readonly')
    await userEvent.click(input)
    await userEvent.keyboard('x')
    await expect.element(input).toHaveValue('Sales')
    await expectNoA11yViolations()
  })

  it('merges a caller className into its wrapper', async () => {
    const screen = await render(<TextField label="Name" className="gap-3" />)
    const wrapper = screen.getByRole('textbox', { name: 'Name' }).element().parentElement

    expect(wrapper).toHaveClass('flex', 'gap-3')
    expect(wrapper).not.toHaveClass('gap-1.5')
    await expectNoA11yViolations()
  })
})

describe('TextareaField', () => {
  it('labels the textarea and links its hint and error', async () => {
    const screen = await render(
      <TextareaField label="Description" hint={hint} error="Enter a description" required />,
    )
    const textarea = screen.getByRole('textbox', { name: 'Description' })

    await expect.element(textarea).toBeVisible()
    await expect.element(textarea).toBeRequired()
    await expect.element(textarea).toHaveAttribute('aria-invalid', 'true')
    await expect.element(textarea).toHaveAccessibleDescription(`${hint} Enter a description`)
    await expect.element(textarea).not.toHaveAttribute('placeholder')
    await expectNoA11yViolations()
  })

  it('shows the focus ring when tabbed to', async () => {
    const screen = await render(<TextareaField label="Description" error="Enter a description" />)
    const textarea = screen.getByRole('textbox', { name: 'Description' })

    await userEvent.tab()
    await expect.element(textarea).toHaveFocus()
    await expect.element(textarea).toHaveStyle(focusRing)
    await expectNoA11yViolations()
  })

  it('accepts multiple lines and resizes only vertically', async () => {
    const screen = await render(<TextareaField label="Description" rows={4} />)
    const textarea = screen.getByRole('textbox', { name: 'Description' })

    await userEvent.click(textarea)
    await userEvent.keyboard('Daily sales{Enter}by region')

    await expect.element(textarea).toHaveValue('Daily sales\nby region')
    await expect.element(textarea).toHaveStyle({ resize: 'vertical' })
    await expect.element(textarea).not.toHaveAttribute('aria-invalid')
    await expectNoA11yViolations()
  })

  it('takes a ref as a prop and is read-only on request', async () => {
    const ref = createRef<HTMLTextAreaElement>()
    const screen = await render(
      <TextareaField label="Description" ref={ref} defaultValue="Daily sales" readOnly />,
    )
    const textarea = screen.getByRole('textbox', { name: 'Description' })

    ref.current?.focus()
    await expect.element(textarea).toHaveFocus()
    await userEvent.keyboard('x')
    await expect.element(textarea).toHaveValue('Daily sales')
    await expect.element(textarea).toHaveAttribute('readonly')
    await expectNoA11yViolations()
  })
})
