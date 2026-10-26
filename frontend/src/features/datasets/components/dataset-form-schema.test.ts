import { describe, expect, it } from 'vitest'
import openapi from '../../../../openapi.json'
import { datasetFieldLimits, datasetFormSchema } from './dataset-form-schema'

const datasetCreate = openapi.components.schemas.DatasetCreate
const fields = ['name', 'owner', 'description'] as const

const valid = {
  name: 'Trade Confirmations',
  owner: 'Middle Office',
  description:
    'Daily export of confirmed trades including instrument type, counterparty, notional value, and settlement date.',
}

const labels = { name: 'Name', owner: 'Owner', description: 'Description' }
const missing = {
  name: 'Enter a name',
  owner: 'Enter an owner',
  description: 'Enter a description',
}

// U+1D538, outside the Basic Multilingual Plane: one code point, two UTF-16 code units.
const astral = '𝔸'

/** The message for each invalid field, keyed by field; empty when the values are valid. */
function messagesFor(values: Record<string, string>): Record<string, string> {
  const result = datasetFormSchema.safeParse(values)
  if (result.success) return {}
  return Object.fromEntries(
    result.error.issues.map(({ path, message }) => [path.join('.'), message] as const),
  )
}

describe('datasetFormSchema', () => {
  it('has the same fields and limits as DatasetCreate in the backend OpenAPI document', () => {
    expect(Object.keys(datasetCreate.properties).toSorted()).toEqual(fields.toSorted())
    expect(datasetCreate.required.toSorted()).toEqual(fields.toSorted())
    for (const field of fields) {
      expect(datasetCreate.properties[field].minLength).toBe(1)
      expect(datasetFieldLimits[field]).toBe(datasetCreate.properties[field].maxLength)
    }
  })

  it('accepts the brief test payload unchanged', () => {
    expect(datasetFormSchema.parse(valid)).toEqual(valid)
  })

  it('trims every field before checking and returning it', () => {
    expect(
      datasetFormSchema.parse({
        name: '  Trade Confirmations ',
        owner: '\tMiddle Office\n',
        description: ` ${valid.description}  `,
      }),
    ).toEqual(valid)
  })

  it.each(fields)('asks for %s when it is empty or only whitespace', (field) => {
    for (const blank of ['', '   ', '\n\t ']) {
      expect(messagesFor({ ...valid, [field]: blank })).toEqual({ [field]: missing[field] })
    }
  })

  it.each(fields)('limits %s to the API maximum in code points, not code units', (field) => {
    const max = datasetFieldLimits[field]
    const atLimit = astral.repeat(max)
    expect(atLimit).toHaveLength(max * 2)

    expect(messagesFor({ ...valid, [field]: atLimit })).toEqual({})
    expect(messagesFor({ ...valid, [field]: ` ${atLimit}  ` })).toEqual({})
    expect(messagesFor({ ...valid, [field]: `${atLimit}a` })).toEqual({
      [field]: `${labels[field]} must be ${String(max)} characters or fewer`,
    })
  })

  it('reports every invalid field at once', () => {
    expect(messagesFor({ name: '', owner: ' ', description: 'x'.repeat(2001) })).toEqual({
      name: 'Enter a name',
      owner: 'Enter an owner',
      description: 'Description must be 2000 characters or fewer',
    })
  })
})
