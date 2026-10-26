import { LoaderCircle } from 'lucide-react'
import { tv } from 'tailwind-variants'

// Rotation is the one motion beyond colour and opacity: a spinner that does not turn reads as a
// static icon. Under reduced motion it stays still, and the label beside it carries the state.
const spinner = tv({ base: 'size-4 shrink-0 motion-safe:animate-spin' })

interface SpinnerProps {
  className?: string
}

export function Spinner({ className }: SpinnerProps) {
  return <LoaderCircle aria-hidden="true" className={spinner({ class: className })} />
}
