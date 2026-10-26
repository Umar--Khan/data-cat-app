import { CircleAlert } from 'lucide-react'
import { useId, type ComponentProps, type ReactNode } from 'react'
import { tv } from 'tailwind-variants'

const field = tv({
  slots: {
    base: 'flex flex-col gap-1.5',
    label: 'text-sm font-medium text-fg',
    hint: 'text-sm text-fg-muted',
    control:
      'w-full rounded-md border border-border-input bg-surface px-3 py-2 text-base text-fg read-only:bg-surface-muted aria-invalid:border-danger',
    error: 'flex gap-1.5 text-sm font-medium text-danger',
    errorIcon: 'mt-0.5 size-4 shrink-0',
  },
  variants: {
    multiline: { true: { control: 'resize-y' } },
  },
})

const styles = field()
const multilineStyles = field({ multiline: true })

interface FieldProps {
  label: string
  hint?: string
  error?: string
}

// The wiring is owned here, so a caller cannot point aria-describedby at a stale id, and there is
// no placeholder: its text disappears on input and fails contrast.
type OwnedAttributes = 'id' | 'placeholder' | 'aria-describedby' | 'aria-invalid'

type TextFieldProps = Omit<ComponentProps<'input'>, OwnedAttributes> & FieldProps
type TextareaFieldProps = Omit<ComponentProps<'textarea'>, OwnedAttributes> & FieldProps

function controlAttributes(id: string, hint?: string, error?: string) {
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(' ')
  return {
    id,
    'aria-describedby': describedBy || undefined,
    'aria-invalid': error ? true : undefined,
  }
}

function FieldFrame({
  id,
  label,
  hint,
  error,
  className,
  children,
}: FieldProps & { id: string; className?: string; children: ReactNode }) {
  return (
    <div className={styles.base({ class: className })}>
      <label htmlFor={id} className={styles.label()}>
        {label}
      </label>
      {hint && (
        <p id={`${id}-hint`} className={styles.hint()}>
          {hint}
        </p>
      )}
      {children}
      {error && (
        <p id={`${id}-error`} className={styles.error()}>
          <CircleAlert aria-hidden="true" className={styles.errorIcon()} />
          {error}
        </p>
      )}
    </div>
  )
}

export function TextField({ label, hint, error, className, ...props }: TextFieldProps) {
  const id = useId()
  return (
    <FieldFrame id={id} label={label} hint={hint} error={error} className={className}>
      <input {...props} {...controlAttributes(id, hint, error)} className={styles.control()} />
    </FieldFrame>
  )
}

export function TextareaField({ label, hint, error, className, ...props }: TextareaFieldProps) {
  const id = useId()
  return (
    <FieldFrame id={id} label={label} hint={hint} error={error} className={className}>
      <textarea
        {...props}
        {...controlAttributes(id, hint, error)}
        className={multilineStyles.control()}
      />
    </FieldFrame>
  )
}
