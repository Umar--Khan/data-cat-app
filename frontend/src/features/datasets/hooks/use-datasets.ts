import {
  useMutation,
  useMutationState,
  useQuery,
  useQueryClient,
  type QueryClient,
} from '@tanstack/react-query'
import { toast } from 'sonner'
import { datasetsApi } from '@/features/datasets/api/datasets-api'
import { datasetKeys } from '@/features/datasets/api/query-keys'
import { ApiError } from '@/lib/api/api-error'
import type { Dataset } from '@/lib/api/schema.gen'

const briefToast = { duration: 5_000 }
const lingeringToast = { duration: 10_000, closeButton: true }

type DatasetRef = Pick<Dataset, 'id' | 'name'>

export function useDatasets() {
  const deletingIds = useMutationState({
    filters: { mutationKey: datasetKeys.delete, status: 'pending' },
    select: (mutation) => (mutation.state.variables as DatasetRef).id,
  })
  return useQuery({
    queryKey: datasetKeys.list,
    queryFn: ({ signal }) => datasetsApi.list(signal),
    // Hiding pending deletes here, rather than removing them from the cache, is what lets
    // overlapping deletes never restore each other's rows, and a failed delete restore its own.
    select: (datasets) => datasets.filter(({ id }) => !deletingIds.includes(id)),
  })
}

export function useCreateDataset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: datasetKeys.create,
    mutationFn: datasetsApi.create,
    // The 201 body is the canonical record, so it is appended rather than refetched.
    onSuccess: async (dataset) => {
      await updateList(queryClient, (datasets) => [...datasets, dataset])
      if (dataset.curation.status === 'completed') {
        toast.success(`Added "${dataset.name}"`, briefToast)
      } else {
        toast.warning(`Saved "${dataset.name}" without AI tags`, {
          ...lingeringToast,
          description: dataset.curation.detail,
        })
      }
    },
  })
}

type DeleteOutcome = 'deleted' | 'already-removed'

// Outcomes are handled in the mutation's own callbacks, not the caller's, so each one is reported
// even when deletes overlap or the row's component has unmounted.
export function useDeleteDataset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationKey: datasetKeys.delete,
    mutationFn: async ({ id }: DatasetRef): Promise<DeleteOutcome> => {
      try {
        await datasetsApi.delete(id)
        return 'deleted'
      } catch (error) {
        // Deleted by someone else first: the catalogue is already in the state the user asked for.
        if (error instanceof ApiError && error.status === 404) return 'already-removed'
        throw error
      }
    },
    onError: (error, dataset) => {
      toast.error(`Couldn't delete "${dataset.name}"`, {
        ...lingeringToast,
        description: error.message,
      })
      // Not awaited, so the mutation stops pending and the row comes back while the list refreshes.
      void queryClient.invalidateQueries({ queryKey: datasetKeys.list })
    },
    // Awaited before the mutation stops pending, so the row is gone from the cache by the time the
    // pending filter lets it through.
    onSuccess: async (outcome, dataset) => {
      await updateList(queryClient, (datasets) => datasets.filter(({ id }) => id !== dataset.id))
      if (outcome === 'deleted') {
        toast.success(`Deleted "${dataset.name}"`, briefToast)
      } else {
        toast.info(`"${dataset.name}" was already removed`, briefToast)
      }
    },
  })
}

async function updateList(queryClient: QueryClient, update: (datasets: Dataset[]) => Dataset[]) {
  // A first load is left alone: cancelling it would revert the list to pending with no fetch left
  // to settle it, and there is nothing to update until it lands.
  if (queryClient.getQueryData(datasetKeys.list) === undefined) return
  // A refresh in flight would overwrite the write with older data, so it is cancelled first.
  const refreshing = queryClient.isFetching({ queryKey: datasetKeys.list }) > 0
  await queryClient.cancelQueries({ queryKey: datasetKeys.list })
  queryClient.setQueryData<Dataset[]>(datasetKeys.list, (datasets) => datasets && update(datasets))
  // The cancelled refresh may be the one a failed delete asked for. Started again, it reads the
  // catalogue after this write.
  if (refreshing) void queryClient.invalidateQueries({ queryKey: datasetKeys.list })
}
