import { Trash2 } from 'lucide-react'
import { useId, type Ref } from 'react'
import { Button } from '@/components/ui/button'
import type { Dataset } from '@/lib/api/schema.gen'
import { CurationBadge } from './curation-badge'
import { TagList } from './tag-list'

interface DatasetCardProps {
  dataset: Dataset
  /** The focusable name heading, so the list can move focus here after a neighbour is deleted. */
  headingRef: Ref<HTMLHeadingElement>
  onDelete: () => void
}

// wrap-anywhere, unlike break-word, also lowers an element's min-content width, so a long unbroken
// name or owner wraps inside the flex rows at 320 px instead of overflowing them.
export function DatasetCard({ dataset, headingRef, onDelete }: DatasetCardProps) {
  const headingId = useId()
  const { name, owner, tags, summary, curation } = dataset
  return (
    <article
      aria-labelledby={headingId}
      className="rounded-lg border border-border bg-surface p-5 shadow-sm sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h3
            ref={headingRef}
            id={headingId}
            tabIndex={-1}
            className="text-base font-semibold wrap-anywhere"
          >
            {name}
          </h3>
          <dl className="mt-1 flex gap-1.5 text-sm">
            <dt className="text-fg-muted">Owner</dt>
            <dd className="min-w-0 wrap-anywhere">{owner}</dd>
          </dl>
        </div>
        <CurationBadge curation={curation} />
      </div>
      <TagList tags={tags} className="mt-3" />
      {/* The API sends a detail exactly when curation failed, and a summary otherwise. */}
      <p className="mt-3 wrap-break-word">
        {curation.status === 'failed' ? curation.detail : summary}
      </p>
      <div className="mt-4 flex justify-end">
        {/* The visible "Delete" starts the accessible name, as WCAG 2.5.3 asks. */}
        <Button variant="secondary" size="sm" onClick={onDelete}>
          <Trash2 aria-hidden="true" className="size-4 shrink-0" />
          Delete<span className="sr-only"> {name}</span>
        </Button>
      </div>
    </article>
  )
}
