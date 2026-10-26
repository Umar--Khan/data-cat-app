import { http, HttpResponse } from 'msw'
import { beforeEach, describe, expect, it } from 'vitest'
import { userEvent } from 'vitest/browser'
import { networkErrorMessage } from '@/lib/api/api-error'
import type { DatasetCreate } from '@/lib/api/schema.gen'
import { expectNoA11yViolations } from '@/test/a11y'
import { emulateMedia } from '@/test/emulate-media'
import { apiUrl, serverError } from '@/test/msw/handlers'
import { createInvalid, hold } from '@/test/msw/scenarios'
import { store } from '@/test/msw/store'
import { apiRequests, worker } from '@/test/msw/worker'
import { renderWithProviders } from '@/test/render'
import { DatasetForm } from './dataset-form'

const fields = ['name', 'owner', 'description'] as const

const tradeConfirmations: DatasetCreate = {
  name: 'Trade Confirmations',
  owner: 'Middle Office',
  description:
    'Daily export of confirmed trades including instrument type, counterparty, notional value, and settlement date.',
}

const missing = {
  name: 'Enter a name',
  owner: 'Enter an owner',
  description: 'Enter a description',
}

const hint = 'What the data contains and how often it updates. Used to generate tags and a summary.'
const pendingMessage = 'Generating tags and a summary. This can take up to 20 seconds.'

// U+1D538, outside the Basic Multilingual Plane: one code point, two UTF-16 code units.
const astral = '𝔸'

async function renderForm() {
  const screen = await renderWithProviders(<DatasetForm />)
  const field = {
    name: screen.getByRole('textbox', { name: 'Name' }),
    owner: screen.getByRole('textbox', { name: 'Owner' }),
    description: screen.getByRole('textbox', { name: 'Description' }),
  }
  return Object.assign(screen, {
    field,
    submitButton: screen.getByRole('button', { name: 'Add dataset' }),
    pendingButton: screen.getByRole('button', { name: 'Saving and curating…' }),
    statusLine: screen.getByRole('status'),
    alert: screen.getByRole('alert'),
    async fill(values: Partial<DatasetCreate>) {
      for (const name of fields) {
        const value = values[name]
        if (value !== undefined) await userEvent.fill(field[name], value)
      }
    },
    async expectValues(values: DatasetCreate) {
      for (const name of fields) await expect.element(field[name]).toHaveValue(values[name])
    },
  })
}

describe('DatasetForm', () => {
  // sonner fades toasts in, and axe fails text caught half-faded. Under reduced motion sonner drops
  // its transitions, so a toast is either transparent, which axe skips, or opaque and checked.
  beforeEach(async () => {
    await emulateMedia([{ name: 'prefers-reduced-motion', value: 'reduce' }])
  })

  it('labels every field, says once that all are required, and starts idle', async () => {
    const screen = await renderForm()

    expect(screen.container.querySelector('form')).toHaveAttribute('novalidate')
    await expect.element(screen.getByText('All fields are required.')).toBeVisible()
    expect(screen.container.textContent).not.toContain('*')
    for (const name of fields) {
      const input = screen.field[name]
      await expect.element(input).toBeRequired()
      await expect.element(input).toHaveValue('')
      await expect.element(input).not.toHaveAttribute('placeholder')
      await expect.element(input).not.toHaveAttribute('maxlength')
      await expect.element(input).not.toHaveAttribute('readonly')
      await expect.element(input).not.toHaveAttribute('aria-invalid')
    }
    await expect.element(screen.field.name).toHaveAttribute('autocomplete', 'off')
    await expect.element(screen.field.owner).toHaveAttribute('autocomplete', 'off')
    await expect.element(screen.field.description).toHaveAccessibleDescription(hint)
    await expect.element(screen.submitButton).toHaveAttribute('type', 'submit')
    await expect.element(screen.submitButton).not.toHaveAttribute('aria-disabled')
    await expect.element(screen.statusLine).toBeEmptyDOMElement()
    await expect.element(screen.alert).not.toBeInTheDocument()
    await expectNoA11yViolations()
  })

  it('sends nothing on an empty submit, shows every message and focuses Name', async () => {
    const screen = await renderForm()

    await userEvent.click(screen.submitButton)

    await expect.element(screen.field.name).toHaveFocus()
    for (const name of fields) {
      await expect.element(screen.field[name]).toHaveAttribute('aria-invalid', 'true')
    }
    await expect.element(screen.field.name).toHaveAccessibleDescription('Enter a name')
    await expect.element(screen.field.owner).toHaveAccessibleDescription('Enter an owner')
    await expect
      .element(screen.field.description)
      .toHaveAccessibleDescription(`${hint} Enter a description`)
    await expect.element(screen.alert).not.toBeInTheDocument()
    expect(apiRequests()).toEqual([])
    await expectNoA11yViolations()
  })

  it.each(fields)('flags only %s when it alone is empty, and focuses it', async (name) => {
    const screen = await renderForm()

    await screen.fill({ ...tradeConfirmations, [name]: '' })
    await userEvent.click(screen.submitButton)

    await expect.element(screen.field[name]).toHaveFocus()
    await expect.element(screen.field[name]).toHaveAttribute('aria-invalid', 'true')
    await expect.element(screen.getByText(missing[name])).toBeVisible()
    for (const other of fields.filter((field) => field !== name)) {
      await expect.element(screen.field[other]).not.toHaveAttribute('aria-invalid')
    }
    expect(apiRequests()).toEqual([])
    await expectNoA11yViolations()
  })

  it('rejects whitespace-only values and keeps them as typed', async () => {
    const screen = await renderForm()
    const blanks = { name: '   ', owner: ' \t ', description: ' \n\n ' }

    await screen.fill(blanks)
    await userEvent.click(screen.submitButton)

    await expect.element(screen.field.name).toHaveFocus()
    await expect.element(screen.field.name).toHaveAccessibleDescription('Enter a name')
    await expect.element(screen.field.owner).toHaveAccessibleDescription('Enter an owner')
    await expect
      .element(screen.field.description)
      .toHaveAccessibleDescription(`${hint} Enter a description`)
    await screen.expectValues(blanks)
    expect(apiRequests()).toEqual([])
    await expectNoA11yViolations()
  })

  it('counts lengths in code points after trimming, and never truncates', async () => {
    const screen = await renderForm()

    await screen.fill({
      name: ` ${astral.repeat(120)}  `,
      owner: 'a'.repeat(121),
      description: 'x'.repeat(2001),
    })
    await userEvent.click(screen.submitButton)

    await expect.element(screen.field.owner).toHaveFocus()
    await expect.element(screen.field.name).not.toHaveAttribute('aria-invalid')
    await expect
      .element(screen.field.owner)
      .toHaveAccessibleDescription('Owner must be 120 characters or fewer')
    await expect
      .element(screen.field.description)
      .toHaveAccessibleDescription(`${hint} Description must be 2000 characters or fewer`)
    await expect.element(screen.field.owner).toHaveValue('a'.repeat(121))
    expect(apiRequests()).toEqual([])
    await expectNoA11yViolations()

    await screen.fill({ owner: 'a'.repeat(120), description: 'x'.repeat(2000) })
    await userEvent.click(screen.submitButton)

    await expect.poll(() => store.list().at(-1)?.name).toBe(astral.repeat(120))
    expect(apiRequests()).toEqual(['POST /datasets'])
    await expectNoA11yViolations()
  })

  it('validates on submit, then on every change once a submit has failed', async () => {
    const screen = await renderForm()

    await userEvent.fill(screen.field.name, 'a'.repeat(121))
    await userEvent.fill(screen.field.owner, 'Middle Office')
    await userEvent.fill(screen.field.owner, '')
    await expect.element(screen.field.name).not.toHaveAttribute('aria-invalid')
    await expect.element(screen.field.owner).not.toHaveAttribute('aria-invalid')

    await userEvent.click(screen.submitButton)
    await expect
      .element(screen.field.name)
      .toHaveAccessibleDescription('Name must be 120 characters or fewer')
    await expect.element(screen.field.owner).toHaveAccessibleDescription('Enter an owner')

    await userEvent.fill(screen.field.name, 'Trade Confirmations')
    await expect.element(screen.field.name).not.toHaveAttribute('aria-invalid')
    await expect.element(screen.field.name).not.toHaveAttribute('aria-describedby')
    await expect.element(screen.field.owner).toHaveAttribute('aria-invalid', 'true')
    await expectNoA11yViolations()

    await userEvent.fill(screen.field.name, '  ')
    await expect.element(screen.field.name).toHaveAccessibleDescription('Enter a name')
    expect(apiRequests()).toEqual([])
    await expectNoA11yViolations()
  })

  it('holds the form while the POST is in flight and ignores a second submit', async () => {
    const gate = hold('POST')
    const screen = await renderForm()
    const statusLine = screen.statusLine.element()

    await screen.fill(tradeConfirmations)
    await userEvent.click(screen.submitButton)
    await gate.arrived

    const button = screen.pendingButton
    await expect.element(button).toHaveFocus()
    await expect.element(button).toHaveAttribute('aria-disabled', 'true')
    await expect.element(button).not.toHaveAttribute('disabled')
    expect(button.element().querySelector('svg')).not.toBeNull()
    await expect.element(screen.statusLine).toHaveTextContent(pendingMessage)
    expect(screen.statusLine.element()).toBe(statusLine)
    for (const name of fields) {
      await expect.element(screen.field[name]).toHaveAttribute('readonly')
    }
    await screen.expectValues(tradeConfirmations)
    await expectNoA11yViolations()

    await userEvent.keyboard('{Enter}')
    await userEvent.keyboard(' ')
    // Playwright treats aria-disabled as not actionable, so force sends the click regardless.
    await userEvent.click(button, { force: true })
    await expect.element(button).toHaveFocus()
    await userEvent.click(screen.field.name)
    await userEvent.keyboard('{Enter}x')
    await expect.element(screen.field.name).toHaveValue(tradeConfirmations.name)
    expect(apiRequests()).toEqual(['POST /datasets'])

    gate.release()
    await expect.element(screen.submitButton).not.toHaveAttribute('aria-disabled')
    await expect.element(screen.statusLine).toBeEmptyDOMElement()
    expect(screen.statusLine.element()).toBe(statusLine)
    for (const name of fields) {
      await expect.element(screen.field[name]).not.toHaveAttribute('readonly')
    }
    expect(apiRequests()).toEqual(['POST /datasets'])
    await expectNoA11yViolations()
  })

  it('adds the brief test payload trimmed, then resets to its first state and focuses Name', async () => {
    const gate = hold('POST')
    const screen = await renderForm()

    // A failed submit first, so the reset has a submitted form to undo.
    await userEvent.click(screen.submitButton)
    await screen.fill({
      name: '  Trade Confirmations ',
      owner: 'Middle Office\t',
      description: ` ${tradeConfirmations.description}\n`,
    })
    await userEvent.click(screen.submitButton)

    const request = await gate.arrived
    expect(await request.clone().json()).toEqual(tradeConfirmations)
    gate.release()

    await expect.element(screen.getByText('Added "Trade Confirmations"')).toBeVisible()
    expect(store.list().at(-1)).toMatchObject({ id: '4', ...tradeConfirmations })
    await expect.element(screen.field.name).toHaveFocus()
    for (const name of fields) {
      await expect.element(screen.field[name]).toHaveValue('')
      await expect.element(screen.field[name]).not.toHaveAttribute('aria-invalid')
    }
    await expect.element(screen.submitButton).toBeVisible()
    await expectNoA11yViolations()

    // Validation is back to on-submit: emptying a field shows nothing until the next submit.
    await userEvent.fill(screen.field.name, 'Trade Confirmations')
    await userEvent.fill(screen.field.name, '')
    await userEvent.fill(screen.field.owner, 'Middle Office')
    await expect.element(screen.field.name).not.toHaveAttribute('aria-invalid')

    await userEvent.click(screen.submitButton)
    await expect.element(screen.field.name).toHaveAccessibleDescription('Enter a name')
    expect(apiRequests()).toEqual(['POST /datasets'])
  })

  it('moves focus to Name after a create when focus is on another of its fields', async () => {
    const gate = hold('POST')
    const screen = await renderForm()

    await screen.fill(tradeConfirmations)
    await userEvent.click(screen.submitButton)
    await gate.arrived
    await userEvent.click(screen.field.owner)
    await expect.element(screen.field.owner).toHaveFocus()
    await expectNoA11yViolations()

    gate.release()
    await expect.element(screen.getByText('Added "Trade Confirmations"')).toBeVisible()
    await expect.element(screen.field.name).toHaveFocus()
    await expectNoA11yViolations()
  })

  it('moves focus to Name after a create when nothing has focus, as Safari leaves it after a click on the button', async () => {
    const gate = hold('POST')
    const screen = await renderForm()

    await screen.fill(tradeConfirmations)
    await userEvent.click(screen.submitButton)
    await gate.arrived
    screen.pendingButton.element().blur()
    expect(document.activeElement).toBe(document.body)
    await expectNoA11yViolations()

    gate.release()
    await expect.element(screen.getByText('Added "Trade Confirmations"')).toBeVisible()
    await expect.element(screen.field.name).toHaveFocus()
    await expectNoA11yViolations()
  })

  it('shows server field errors on their fields, focuses the first in form order, and keeps the values', async () => {
    createInvalid([
      { field: 'description', message: 'This field must be at most 2000 characters.' },
      { field: 'owner', message: 'This field must not be blank.' },
    ])
    const screen = await renderForm()

    await screen.fill(tradeConfirmations)
    await userEvent.click(screen.submitButton)

    await expect.element(screen.field.owner).toHaveFocus()
    await expect.element(screen.field.owner).toHaveAttribute('aria-invalid', 'true')
    await expect
      .element(screen.field.owner)
      .toHaveAccessibleDescription('This field must not be blank.')
    await expect
      .element(screen.field.description)
      .toHaveAccessibleDescription(`${hint} This field must be at most 2000 characters.`)
    await expect.element(screen.field.name).not.toHaveAttribute('aria-invalid')
    await expect.element(screen.alert).not.toBeInTheDocument()
    await expect.element(screen.submitButton).not.toHaveAttribute('aria-disabled')
    await screen.expectValues(tradeConfirmations)
    await expectNoA11yViolations()

    // The failed submit turned on validation on change, which clears a server error on an edit
    // that passes, and leaves the other field's error alone.
    await userEvent.fill(screen.field.owner, 'Back Office')
    await expect.element(screen.field.owner).not.toHaveAttribute('aria-invalid')
    await expect.element(screen.field.description).toHaveAttribute('aria-invalid', 'true')
    await expectNoA11yViolations()
  })

  it('shows a 400 that names no form field as an alert above the submit button', async () => {
    createInvalid([{ field: 'tags', message: 'This field is not allowed.' }])
    const screen = await renderForm()

    await screen.fill(tradeConfirmations)
    await userEvent.click(screen.submitButton)

    await expect
      .element(screen.alert)
      .toHaveTextContent("Couldn't add the datasetThe request body has an invalid field: tags.")
    const position = screen.alert.element().compareDocumentPosition(screen.submitButton.element())
    expect(position & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    for (const name of fields) {
      await expect.element(screen.field[name]).not.toHaveAttribute('aria-invalid')
    }
    await expect.element(screen.submitButton).toHaveFocus()
    await screen.expectValues(tradeConfirmations)
    await expectNoA11yViolations()
  })

  it('shows a server error as an alert, keeps the values, and clears it on the next attempt', async () => {
    worker.use(http.post(apiUrl('/datasets'), () => serverError('/datasets'), { once: true }))
    const screen = await renderForm()

    await screen.fill(tradeConfirmations)
    await userEvent.click(screen.submitButton)

    await expect
      .element(screen.alert)
      .toHaveTextContent("Couldn't add the datasetThe server hit an unexpected error.")
    await expect.element(screen.submitButton).toHaveFocus()
    await screen.expectValues(tradeConfirmations)
    await expectNoA11yViolations()

    const gate = hold('POST')
    await userEvent.click(screen.submitButton)
    await gate.arrived
    await expect.element(screen.alert).not.toBeInTheDocument()

    gate.release()
    await expect.element(screen.getByText('Added "Trade Confirmations"')).toBeVisible()
    expect(apiRequests()).toEqual(['POST /datasets', 'POST /datasets'])
    await expectNoA11yViolations()
  })

  it('shows a network failure as an alert and keeps the values', async () => {
    worker.use(http.post(apiUrl('/datasets'), () => HttpResponse.error()))
    const screen = await renderForm()

    await screen.fill(tradeConfirmations)
    await userEvent.click(screen.submitButton)

    await expect
      .element(screen.alert)
      .toHaveTextContent(`Couldn't add the dataset${networkErrorMessage}`)
    await screen.expectValues(tradeConfirmations)
    await expect.element(screen.submitButton).not.toHaveAttribute('aria-disabled')
    await expectNoA11yViolations()
  })
})
