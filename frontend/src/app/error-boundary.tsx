import { Component, type ReactNode } from 'react'
import { reloadPage } from '@/app/reload-page'
import { Button } from '@/components/ui/button'

// The failure replaces the whole page, focused element included, so focus moves to the heading
// and a screen reader announces what happened instead of falling silent on the body.
function focusOnMount(heading: HTMLHeadingElement | null) {
  heading?.focus()
}

function RenderFailure() {
  return (
    <main className="mx-auto flex max-w-3xl flex-col items-start gap-3 px-4 py-10 sm:px-6">
      <h1 ref={focusOnMount} tabIndex={-1} className="text-2xl font-semibold">
        Something went wrong
      </h1>
      <p className="text-fg-muted">
        The page hit an unexpected error. Reload it to carry on; saved datasets are not affected.
      </p>
      <Button className="mt-3" onClick={reloadPage}>
        Reload page
      </Button>
    </main>
  )
}

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  failed: boolean
}

// A class because React has no hook for catching render errors. React itself logs what it catches.
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  override state: ErrorBoundaryState = { failed: false }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { failed: true }
  }

  override render() {
    return this.state.failed ? <RenderFailure /> : this.props.children
  }
}
