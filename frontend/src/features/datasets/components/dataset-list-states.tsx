import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

// Static rather than pulsing: a pulse is a looping opacity animation far longer than the 150 ms
// motion budget, and the status region already says the list is loading.
function SkeletonCard() {
  return (
    <div
      aria-hidden="true"
      className="flex flex-col gap-3 rounded-lg border border-border bg-surface p-5 shadow-sm sm:p-6"
    >
      <div className="h-5 w-2/5 rounded-sm bg-surface-muted" />
      <div className="h-4 w-1/4 rounded-sm bg-surface-muted" />
      <div className="h-4 w-4/5 rounded-sm bg-surface-muted" />
    </div>
  )
}

export function DatasetListSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <SkeletonCard />
      <SkeletonCard />
      <SkeletonCard />
    </div>
  )
}

export function DatasetListEmpty() {
  return (
    <p className="rounded-lg border border-dashed border-border p-6 text-center text-fg-muted">
      No datasets yet. Add one with the Add a dataset form.
    </p>
  )
}

interface RetryProps {
  retrying?: boolean
  onRetry: () => void
}

function RetryButton({ retrying, onRetry }: RetryProps) {
  return (
    <Button variant="secondary" size="sm" pending={retrying} onClick={onRetry}>
      Try again
    </Button>
  )
}

// No pending state: a retry with nothing loaded puts the query back to pending, which replaces
// this alert with the skeleton as soon as it starts.
export function DatasetListLoadError({
  message,
  onRetry,
}: {
  message: string
  onRetry: () => void
}) {
  return (
    <Alert tone="danger" title="Couldn't load datasets" action={<RetryButton onRetry={onRetry} />}>
      {message}
    </Alert>
  )
}

// The stale list stays on screen while a retry runs, so the warning shows it is in progress.
export function DatasetListRefreshError(retry: Required<RetryProps>) {
  return (
    <Alert
      tone="warning"
      title="Couldn't refresh. Showing the last loaded list."
      action={<RetryButton {...retry} />}
    />
  )
}
