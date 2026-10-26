import type { LucideIcon } from 'lucide-react'
import type { ComponentProps } from 'react'
import { tv, type VariantProps } from 'tailwind-variants'

// The transparent border becomes visible in forced-colours mode, where backgrounds are dropped.
const badge = tv({
  slots: {
    base: 'inline-flex items-center gap-1 rounded-sm border border-transparent px-1.5 py-0.5 text-xs font-medium',
    icon: 'size-3.5 shrink-0',
  },
  variants: {
    tone: {
      accent: { base: 'bg-accent-subtle text-accent-subtle-fg' },
      neutral: { base: 'bg-surface-muted text-fg-muted' },
      warning: { base: 'bg-warning-subtle text-warning-fg' },
    },
  },
  defaultVariants: { tone: 'neutral' },
})

// Children are a string so a badge always carries text; the icon only reinforces it.
type BadgeProps = Omit<ComponentProps<'span'>, 'children'> &
  VariantProps<typeof badge> & {
    icon?: LucideIcon
    children: string
  }

export function Badge({ tone, icon: Icon, className, children, ...props }: BadgeProps) {
  const styles = badge({ tone })
  return (
    <span {...props} className={styles.base({ class: className })}>
      {Icon && <Icon aria-hidden="true" className={styles.icon()} />}
      {children}
    </span>
  )
}
