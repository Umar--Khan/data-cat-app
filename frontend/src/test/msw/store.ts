import type { Dataset, DatasetCreate } from '@/lib/api/schema.gen'

export type Curated = Pick<Dataset, 'tags' | 'summary' | 'curation'>

const seedCreatedAt = '2026-10-25T09:00:00Z'
const handCurated = { status: 'completed', provider: 'seed', detail: null } as const

export const seedDatasets: readonly Dataset[] = [
  {
    id: '1',
    name: 'Customer Transactions',
    owner: 'Finance Team',
    description:
      'Contains daily transaction records including transaction ID, customer ID, amount, currency, and timestamp.',
    tags: ['finance', 'transactions', 'PII', 'daily'],
    summary:
      'A daily feed of customer transaction records covering amounts, currencies, and timestamps.',
    curation: handCurated,
    createdAt: seedCreatedAt,
  },
  {
    id: '2',
    name: 'Product Inventory',
    owner: 'Operations Team',
    description:
      'Snapshot of warehouse stock levels by SKU, including product name, quantity on hand, and reorder threshold.',
    tags: ['inventory', 'operations', 'warehouse'],
    summary: 'A warehouse snapshot tracking stock levels and reorder thresholds per product SKU.',
    curation: handCurated,
    createdAt: seedCreatedAt,
  },
  {
    id: '3',
    name: 'Employee Directory',
    owner: 'HR Team',
    description:
      'List of current employees with name, department, role, and office location. Updated weekly.',
    tags: ['HR', 'PII', 'employees', 'weekly'],
    summary: 'A weekly-refreshed directory of employees including role, department, and location.',
    curation: handCurated,
    createdAt: seedCreatedAt,
  },
]

export function keywordCurated({ name }: DatasetCreate): Curated {
  return {
    tags: ['catalogue'],
    summary: `A dataset named ${name}.`,
    curation: { status: 'completed', provider: 'keyword', detail: null },
  }
}

export const failedCuration: Curated = {
  tags: [],
  summary: null,
  curation: {
    status: 'failed',
    provider: 'anthropic',
    detail: 'The AI service could not be reached.',
  },
}

let datasets: Dataset[]
let nextId: number

/** The mock API's catalogue: ids count on from the records it starts with and are never reused. */
export const store = {
  list: (): Dataset[] => [...datasets],
  add(input: DatasetCreate, curated: Curated): Dataset {
    const dataset = {
      id: String(nextId++),
      ...input,
      ...curated,
      createdAt: new Date().toISOString(),
    }
    datasets.push(dataset)
    return dataset
  },
  remove(id: string): Dataset | undefined {
    const removed = datasets.find((dataset) => dataset.id === id)
    datasets = datasets.filter((dataset) => dataset !== removed)
    return removed
  },
  reset(initial: readonly Dataset[] = seedDatasets) {
    datasets = [...initial]
    nextId = Math.max(0, ...initial.map(({ id }) => Number(id))) + 1
  },
}

store.reset()
