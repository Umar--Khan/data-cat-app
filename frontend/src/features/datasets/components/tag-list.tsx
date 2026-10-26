import { cn } from 'tailwind-variants'

interface TagListProps {
  tags: readonly string[]
  className?: string
}

// Text rather than an empty list, which a screen reader would announce as "list, 0 items".
export function TagList({ tags, className }: TagListProps) {
  if (tags.length === 0) {
    return <p className={cn('text-xs text-fg-muted', className)}>No tags</p>
  }
  // Curation de-duplicates tags, so each one is a stable key. wrap-anywhere lets an unbroken tag
  // shrink below its own width inside the flex row instead of pushing the page sideways at 320 px.
  return (
    <ul aria-label="Tags" className={cn('flex flex-wrap gap-1.5', className)}>
      {tags.map((tag) => (
        <li
          key={tag}
          className="max-w-full rounded-sm bg-surface-muted px-1.5 py-0.5 text-xs wrap-anywhere text-fg-muted"
        >
          {tag}
        </li>
      ))}
    </ul>
  )
}
