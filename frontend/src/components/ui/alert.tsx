import { CircleAlert, TriangleAlert } from 'lucide-react'
import type { ComponentProps, ReactNode } from 'react'
import { tv, type VariantProps } from 'tailwind-variants'

const alert = tv({
  slots: {
    base: 'flex gap-3 rounded-md border p-4',
    icon: 'mt-0.5 size-4 shrink-0',
    content: 'min-w-0 flex-1',
    title: 'text-sm font-semibold',
    body: 'mt-1 text-sm text-fg',
    action: 'mt-3',
  },
  variants: {
    tone: {
      danger: {
        base: 'border-danger/30 bg-danger-subtle',
        icon: 'text-danger',
        title: 'text-danger',
      },
      warning: {
        base: 'border-warning-fg/30 bg-warning-subtle',
        icon: 'text-warning-fg',
        title: 'text-warning-fg',
      },
    },
  },
})

// No live role by default: the list's failure alerts are announced by its status region, and a
// second announcement would repeat it. Only an error that follows a user action asks for "alert".
type AlertProps = Omit<ComponentProps<'div'>, 'title' | 'role'> &
  Required<VariantProps<typeof alert>> & {
    title: string
    action?: ReactNode
    role?: 'alert'
  }

export function Alert({ tone, title, action, className, children, ...props }: AlertProps) {
  const styles = alert({ tone })
  const Icon = tone === 'warning' ? TriangleAlert : CircleAlert
  return (
    <div {...props} className={styles.base({ class: className })}>
      <Icon aria-hidden="true" className={styles.icon()} />
      <div className={styles.content()}>
        <p className={styles.title()}>{title}</p>
        {children ? <div className={styles.body()}>{children}</div> : null}
        {action ? <div className={styles.action()}>{action}</div> : null}
      </div>
    </div>
  )
}
