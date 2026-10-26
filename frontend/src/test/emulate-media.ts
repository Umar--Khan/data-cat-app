/// <reference types="@vitest/browser-playwright" />
import { onTestFinished } from 'vitest'
import { cdp } from 'vitest/browser'

/** Emulates CSS media features such as forced-colors for the rest of the current test. */
export async function emulateMedia(features: { name: string; value: string }[]): Promise<void> {
  await cdp().send('Emulation.setEmulatedMedia', { features })
  onTestFinished(async () => {
    await cdp().send('Emulation.setEmulatedMedia', { features: [] })
  })
}
