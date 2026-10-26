import type { UseQueryResult } from '@tanstack/react-query'
import { useEffect, useRef, useState, type RefObject } from 'react'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { useDatasets, useDeleteDataset } from '@/features/datasets/hooks/use-datasets'
import type { Dataset } from '@/lib/api/schema.gen'
import { DatasetCard } from './dataset-card'
import {
  DatasetListEmpty,
  DatasetListLoadError,
  DatasetListRefreshError,
  DatasetListSkeleton,
} from './dataset-list-states'

// A retry after a failed load goes back to pending, so it reads "Loading" again, and a refresh
// failure is cleared while a retry runs, so a repeated failure is announced afresh.
function statusMessage({
  isPending,
  isLoadingError,
  isRefetchError,
  isFetching,
}: Pick<UseQueryResult, 'isPending' | 'isLoadingError' | 'isRefetchError' | 'isFetching'>): string {
  if (isLoadingError) return "Couldn't load datasets"
  if (isRefetchError && !isFetching) return "Couldn't refresh. Showing the last loaded list."
  return isPending ? 'Loading datasets…' : ''
}

interface DatasetListProps {
  /**
   * The section's "Datasets" heading. It takes focus when a delete leaves no row to move to, and
   * on Try again, whose alert is about to go.
   */
  headingRef: RefObject<HTMLElement | null>
}

interface FocusAfterRemoval {
  removedId: string
  target: HTMLElement | null
}

export function DatasetList({ headingRef }: DatasetListProps) {
  const list = useDatasets()
  const { mutate: deleteDataset } = useDeleteDataset()
  const [selected, setSelected] = useState<Dataset>()
  const [confirming, setConfirming] = useState(false)
  const headingsRef = useRef(new Map<string, HTMLElement | null>())
  const focusAfterRemovalRef = useRef<FocusAfterRemoval>(null)
  const datasets = list.data ?? []

  // Runs after every commit, not on a dependency, so it acts on the first one without the row even
  // if the list it renders happens to be unchanged. Clearing the request first is what keeps a
  // later refetch or delete outcome from moving focus again.
  useEffect(() => {
    const request = focusAfterRemovalRef.current
    if (request === null || datasets.some(({ id }) => id === request.removedId)) return
    focusAfterRemovalRef.current = null
    request.target?.focus()
  })

  // The target is chosen while the row is still in the list, because once the delete is pending
  // the row is filtered out and its neighbours can no longer be found from it.
  function confirmDelete(dataset: Dataset) {
    const index = datasets.findIndex(({ id }) => id === dataset.id)
    // A refresh can remove the row while its dialog is open, and then it has no neighbours.
    const neighbour = index === -1 ? undefined : (datasets[index + 1] ?? datasets[index - 1])
    focusAfterRemovalRef.current = {
      removedId: dataset.id,
      target: (neighbour && headingsRef.current.get(neighbour.id)) ?? headingRef.current,
    }
    deleteDataset(dataset)
  }

  // A retry after a failed load swaps the alert for the skeleton at once, and a successful refresh
  // retry removes its warning, so focus would fall to the body with the button it was on.
  function retry() {
    headingRef.current?.focus()
    void list.refetch()
  }

  return (
    <div className="flex flex-col gap-3">
      <p role="status" className="sr-only">
        {statusMessage(list)}
      </p>
      {list.isPending && <DatasetListSkeleton />}
      {list.isLoadingError && <DatasetListLoadError message={list.error.message} onRetry={retry} />}
      {list.isRefetchError && (
        <DatasetListRefreshError retrying={list.isFetching} onRetry={retry} />
      )}
      {list.data &&
        (list.data.length > 0 ? (
          <ul className="flex flex-col gap-3">
            {list.data.map((dataset) => (
              <li key={dataset.id}>
                <DatasetCard
                  dataset={dataset}
                  headingRef={(heading) => {
                    headingsRef.current.set(dataset.id, heading)
                    return () => {
                      headingsRef.current.delete(dataset.id)
                    }
                  }}
                  onDelete={() => {
                    setSelected(dataset)
                    setConfirming(true)
                  }}
                />
              </li>
            ))}
          </ul>
        ) : (
          <DatasetListEmpty />
        ))}
      {/* Kept mounted once used: its close event must reach onClose even after the last row goes. */}
      {selected && (
        <ConfirmDialog
          open={confirming}
          title={`Delete "${selected.name}"?`}
          description="It will be removed from the catalogue. This can't be undone."
          confirmLabel="Delete dataset"
          onClose={() => {
            setConfirming(false)
          }}
          onConfirm={() => {
            confirmDelete(selected)
          }}
        />
      )}
    </div>
  )
}
