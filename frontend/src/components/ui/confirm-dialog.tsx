import { useEffect, useId, useRef } from 'react'
import { tv } from 'tailwind-variants'
import { Button } from './button'

// Preflight zeroes every margin, so the modal needs m-auto back to sit in the middle of the viewport.
const confirmDialog = tv({
  slots: {
    base: 'm-auto w-[calc(100%-2rem)] max-w-md rounded-lg border border-border bg-surface p-6 text-fg shadow-lg backdrop:bg-fg/40',
    title: 'text-lg font-semibold wrap-break-word',
    description: 'mt-2 wrap-break-word text-fg-muted',
    actions: 'mt-6 flex flex-wrap justify-end gap-3',
  },
})

const styles = confirmDialog()

interface ConfirmDialogProps {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  /** Runs after every close, whether by Esc, Cancel or confirm, so the caller can set `open` back. */
  onClose: () => void
  /** Runs after the dialog has closed, so focus the caller moves here is not taken back by it. */
  onConfirm: () => void
  className?: string
}

// showModal() supplies the top layer, the inert background, Esc and focus return to the opener.
// Cancel comes first, so it is the control the browser focuses on open.
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  onClose,
  onConfirm,
  className,
}: ConfirmDialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    if (open) ref.current?.showModal()
    else ref.current?.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      role="alertdialog"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      className={styles.base({ class: className })}
      onClose={onClose}
    >
      <h2 id={titleId} className={styles.title()}>
        {title}
      </h2>
      <p id={descriptionId} className={styles.description()}>
        {description}
      </p>
      <div className={styles.actions()}>
        <Button variant="secondary" onClick={() => ref.current?.close()}>
          Cancel
        </Button>
        <Button
          variant="danger"
          onClick={() => {
            ref.current?.close()
            onConfirm()
          }}
        >
          {confirmLabel}
        </Button>
      </div>
    </dialog>
  )
}
