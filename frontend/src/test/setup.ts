// The real stylesheet, so axe measures contrast and focus rings as users see them.
import '@/index.css'
import { toast } from 'sonner'
import { afterAll, beforeAll, beforeEach } from 'vitest'
import { resetMockApi, startMockApi, worker } from '@/test/msw/worker'

beforeAll(async () => {
  await startMockApi()
})

beforeEach(() => {
  resetMockApi()
  // sonner keeps toasts in module state and replays active ones to a newly mounted Toaster.
  toast.dismiss()
})

afterAll(async () => {
  await worker.stop()
})
