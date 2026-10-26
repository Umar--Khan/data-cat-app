import { unwrap } from '@/lib/api/api-error'
import { apiClient } from '@/lib/api/client'
import type { DatasetCreate } from '@/lib/api/schema.gen'

export const datasetsApi = {
  list: (signal?: AbortSignal) => unwrap(apiClient.GET('/datasets', { signal })),
  create: (body: DatasetCreate) => unwrap(apiClient.POST('/datasets', { body })),
  delete: (id: string) => unwrap(apiClient.DELETE('/datasets/{id}', { params: { path: { id } } })),
}
