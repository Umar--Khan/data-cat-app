import type { FieldPath, FieldValues, UseFormSetError } from 'react-hook-form'
import type { ApiError } from '@/lib/api/api-error'

/**
 * Shows an ApiError's field errors on the form fields they name and focuses the first of them,
 * in the order of `fields`, so focus lands where it would after a failed client-side submit.
 * Returns false when no field error names one of `fields`, so the caller shows the error message
 * instead.
 */
export function applyServerErrors<TFieldValues extends FieldValues>(
  error: ApiError,
  setError: UseFormSetError<TFieldValues>,
  fields: readonly FieldPath<TFieldValues>[],
): boolean {
  const matched = fields.flatMap((field) => {
    const fieldError = error.fieldErrors.find((entry) => entry.field === field)
    return fieldError ? [{ field, message: fieldError.message }] : []
  })
  matched.forEach(({ field, message }, index) => {
    setError(field, { type: 'server', message }, { shouldFocus: index === 0 })
  })
  return matched.length > 0
}
