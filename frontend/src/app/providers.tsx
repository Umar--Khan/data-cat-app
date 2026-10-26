import { QueryClientProvider } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { Toaster as SonnerToaster } from 'sonner'
import { createQueryClient } from '@/app/query-client'

// Focus events only come from elements.
function toastList(event: FocusEvent): Element | null {
  return (event.target as Element).closest('[data-sonner-toaster]')
}

// sonner pauses its timers only while the stack is expanded, which hover and Alt+T do, or pressed.
// A toast reached with Tab would keep counting down and could vanish with focus on it, and in a
// collapsed stack Tab would also land on toasts whose content is hidden. Expanding the stack on
// focus, through the mouse events sonner listens for, pauses every toast and lays them all out.
function expandWhileFocused(region: HTMLElement) {
  function expand(event: FocusEvent) {
    toastList(event)?.dispatchEvent(new MouseEvent('mousemove', { bubbles: true }))
  }
  function collapse(event: FocusEvent) {
    const list = toastList(event)
    const stillInside = event.relatedTarget instanceof Node && list?.contains(event.relatedTarget)
    // A pointer still over the stack keeps it expanded, as it would without focus.
    if (!list || stillInside || list.matches(':hover')) return
    list.dispatchEvent(new MouseEvent('mouseout', { bubbles: true }))
  }
  region.addEventListener('focusin', expand)
  region.addEventListener('focusout', collapse)
  return () => {
    region.removeEventListener('focusin', expand)
    region.removeEventListener('focusout', collapse)
  }
}

// The collapsed stack is as tall as its front toast, which a long dataset name or enlarged text
// can make taller than any fixed allowance. sonner measures that toast onto the list it renders;
// a copy on the root lets the scroll padding in src/index.css keep focus clear of the stack.
function shareFrontToastHeight(region: HTMLElement) {
  const root = document.documentElement
  const observer = new MutationObserver(() => {
    const list = region.querySelector<HTMLElement>('[data-sonner-toaster]')
    const height = list?.style.getPropertyValue('--front-toast-height')
    if (height) root.style.setProperty('--front-toast-height', height)
    else root.style.removeProperty('--front-toast-height')
  })
  observer.observe(region, { childList: true, subtree: true, attributeFilter: ['style'] })
  return () => {
    observer.disconnect()
    root.style.removeProperty('--front-toast-height')
  }
}

function enhanceToastRegion(region: HTMLElement) {
  const stopExpanding = expandWhileFocused(region)
  const stopSharing = shareFrontToastHeight(region)
  return () => {
    stopExpanding()
    stopSharing()
  }
}

/**
 * The app's notification stack. Durations and close buttons are set on each toast by type, so the
 * stack leaves closeButton off: sonner would otherwise give success and info toasts one too.
 * Colours, the close button's size and the focus ring come from src/index.css.
 */
export function Toaster() {
  return (
    <SonnerToaster ref={enhanceToastRegion} position="bottom-right" visibleToasts={3} richColors />
  )
}

export function Providers({ children }: { children: ReactNode }) {
  // Created once: a new client on a later render would start from an empty cache.
  const [queryClient] = useState(createQueryClient)
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <Toaster />
    </QueryClientProvider>
  )
}
