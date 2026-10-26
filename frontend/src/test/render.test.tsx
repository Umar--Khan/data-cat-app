import { toast } from 'sonner'
import { describe, expect, it } from 'vitest'
import { page } from 'vitest/browser'
import { renderHookWithProviders, renderWithProviders } from './render'

async function toastElement(title: string): Promise<Element | null> {
  const text = page.getByText(title, { exact: true })
  await expect.element(text).toBeInTheDocument()
  return text.element().closest('[data-sonner-toast]')
}

// Component tests scan toasts with axe, so they must see the app's toaster and its colours.
describe('test render helpers', () => {
  it('renderWithProviders mounts the app toaster', async () => {
    await renderWithProviders(<p>Page</p>)
    toast.error('Failed')

    expect(await toastElement('Failed')).toHaveAttribute('data-rich-colors', 'true')
  })

  it('renderHookWithProviders mounts the app toaster', async () => {
    await renderHookWithProviders(() => null)
    toast.error('Failed')

    expect(await toastElement('Failed')).toHaveAttribute('data-rich-colors', 'true')
  })
})
