import type { ComponentProps } from 'react'
import { tv, type VariantProps } from 'tailwind-variants'
import { Spinner } from './spinner'

// The transparent border becomes visible in forced-colours mode, where backgrounds are dropped.
// Only the background transitions: transition-colors would also fade the focus ring in from the
// text colour, which is white on the primary and danger buttons.
const button = tv({
  base: [
    'inline-flex items-center justify-center gap-2 rounded-md border border-transparent text-sm font-medium',
    'aria-disabled:cursor-progress motion-safe:transition-[background-color] motion-safe:duration-150',
  ],
  variants: {
    variant: {
      primary: 'bg-accent text-on-accent hover:not-aria-disabled:bg-accent-hover',
      secondary: 'border-border-input bg-surface text-fg hover:not-aria-disabled:bg-surface-muted',
      danger: 'bg-danger text-on-accent hover:not-aria-disabled:bg-danger-hover',
    },
    size: {
      md: 'min-h-10 px-4 py-2',
      sm: 'min-h-8 px-3 py-1',
    },
  },
  defaultVariants: { variant: 'primary', size: 'md' },
})

type ButtonProps = ComponentProps<'button'> &
  VariantProps<typeof button> & {
    pending?: boolean
  }

export function Button({
  variant,
  size,
  pending = false,
  type = 'button',
  className,
  onClick,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      type={type}
      // Not `disabled`: a disabled button drops focus, and a pending button keeps it.
      aria-disabled={pending || undefined}
      className={button({ variant, size, class: className })}
      onClick={(event) => {
        if (pending) {
          // Also cancels the form submission a submit button's click would start, including the
          // implicit one that Enter in a text field triggers.
          event.preventDefault()
          return
        }
        onClick?.(event)
      }}
    >
      {pending && <Spinner />}
      {children}
    </button>
  )
}
