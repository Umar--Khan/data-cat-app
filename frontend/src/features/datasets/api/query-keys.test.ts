import { describe, expect, it } from 'vitest'
import { datasetKeys } from './query-keys'

describe('datasetKeys', () => {
  it('names the list query and both mutations under datasets', () => {
    expect(datasetKeys).toEqual({
      list: ['datasets', 'list'],
      create: ['datasets', 'create'],
      delete: ['datasets', 'delete'],
    })
  })
})
