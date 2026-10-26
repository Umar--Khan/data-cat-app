import { useForm } from 'react-hook-form'
import { describe, expect, it, vi } from 'vitest'
import { userEvent } from 'vitest/browser'
import { render } from 'vitest-browser-react'
import { TextField } from '@/components/ui/field'
import { ApiError } from '@/lib/api/api-error'
import type { DatasetCreate, FieldError } from '@/lib/api/schema.gen'
import { expectNoA11yViolations } from '@/test/a11y'
import { applyServerErrors } from './apply-server-errors'

const fields = ['name', 'owner', 'description'] as const
const labels = { name: 'Name', owner: 'Owner', description: 'Description' }

function invalid(fieldErrors: FieldError[]) {
  return new ApiError({ status: 400, message: 'Invalid request body', fieldErrors })
}

function ServerErrorsForm({
  error,
  onApply,
}: {
  error: ApiError
  onApply: (matched: boolean) => void
}) {
  const {
    register,
    setError,
    formState: { errors },
  } = useForm<DatasetCreate>()
  return (
    <form aria-label="Dataset">
      {fields.map((field) => (
        <TextField
          key={field}
          label={labels[field]}
          error={errors[field]?.message}
          {...register(field)}
        />
      ))}
      <button
        type="button"
        onClick={() => {
          onApply(applyServerErrors(error, setError, fields))
        }}
      >
        Apply
      </button>
    </form>
  )
}

async function renderAndApply(error: ApiError) {
  const onApply = vi.fn<(matched: boolean) => void>()
  const screen = await render(<ServerErrorsForm error={error} onApply={onApply} />)
  await userEvent.click(screen.getByRole('button', { name: 'Apply' }))
  return { screen, onApply }
}

describe('applyServerErrors', () => {
  it('shows field errors on the fields they name and focuses the first in form order', async () => {
    const { screen, onApply } = await renderAndApply(
      invalid([
        { field: 'description', message: 'This field must be at most 2000 characters.' },
        { field: 'owner', message: 'This field must not be blank.' },
      ]),
    )
    const owner = screen.getByRole('textbox', { name: 'Owner' })
    const description = screen.getByRole('textbox', { name: 'Description' })

    expect(onApply).toHaveBeenCalledWith(true)
    await expect.element(owner).toHaveFocus()
    await expect.element(owner).toHaveAttribute('aria-invalid', 'true')
    await expect.element(owner).toHaveAccessibleDescription('This field must not be blank.')
    await expect
      .element(description)
      .toHaveAccessibleDescription('This field must be at most 2000 characters.')
    await expect
      .element(screen.getByRole('textbox', { name: 'Name' }))
      .not.toHaveAttribute('aria-invalid')
    await expectNoA11yViolations()
  })

  it('ignores field errors for fields the form does not have', async () => {
    const { screen, onApply } = await renderAndApply(
      invalid([
        { field: 'tags', message: 'This field is not allowed.' },
        { field: 'name', message: 'This field is required.' },
      ]),
    )
    const name = screen.getByRole('textbox', { name: 'Name' })

    expect(onApply).toHaveBeenCalledWith(true)
    await expect.element(name).toHaveFocus()
    await expect.element(name).toHaveAccessibleDescription('This field is required.')
    await expect.element(screen.getByText('This field is not allowed.')).not.toBeInTheDocument()
  })

  it('keeps the first message when a field is named twice', async () => {
    const { screen } = await renderAndApply(
      invalid([
        { field: 'name', message: 'This field must not be blank.' },
        { field: 'name', message: 'This field must be a string.' },
      ]),
    )

    await expect
      .element(screen.getByRole('textbox', { name: 'Name' }))
      .toHaveAccessibleDescription('This field must not be blank.')
  })

  it.each([
    ['no field errors', []],
    ['only unknown fields', [{ field: 'id', message: 'This field is not allowed.' }]],
  ])('reports no match and sets nothing for %s', async (_, fieldErrors) => {
    const { screen, onApply } = await renderAndApply(invalid(fieldErrors))

    expect(onApply).toHaveBeenCalledWith(false)
    for (const field of fields) {
      await expect
        .element(screen.getByRole('textbox', { name: labels[field] }))
        .not.toHaveAttribute('aria-invalid')
    }
    await expect.element(screen.getByRole('button', { name: 'Apply' })).toHaveFocus()
  })
})
