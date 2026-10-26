import { z } from 'zod'
import type { DatasetCreate } from '@/lib/api/schema.gen'

/** The API's maximum length for each field, in code points after trimming. */
export const datasetFieldLimits = {
  name: 120,
  owner: 120,
  description: 2000,
} as const satisfies Record<keyof DatasetCreate, number>

// zod's max() counts UTF-16 code units, so an emoji would count as two characters where the API
// counts one.
function codePointLength(value: string): number {
  return Array.from(value).length
}

function requiredText(label: string, missingMessage: string, maxLength: number) {
  return z
    .string()
    .trim()
    .min(1, missingMessage)
    .refine(
      (value) => codePointLength(value) <= maxLength,
      `${label} must be ${String(maxLength)} characters or fewer`,
    )
}

export const datasetFormSchema = z.object({
  name: requiredText('Name', 'Enter a name', datasetFieldLimits.name),
  owner: requiredText('Owner', 'Enter an owner', datasetFieldLimits.owner),
  description: requiredText('Description', 'Enter a description', datasetFieldLimits.description),
}) satisfies z.ZodType<DatasetCreate, DatasetCreate>
