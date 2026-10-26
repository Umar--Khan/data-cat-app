import { defineConfig, devices } from '@playwright/test'
import { apiPort, apiUrl, webPort, webUrl } from './e2e/urls.ts'

const ci = Boolean(process.env.CI)

export default defineConfig({
  testDir: 'e2e',
  // Every test shares the API's in-memory catalogue, so tests run one at a time and each one
  // deletes what it created (specs/quality-gates.md, E2E harness).
  workers: 1,
  fullyParallel: false,
  forbidOnly: ci,
  retries: ci ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: webUrl,
    reducedMotion: 'reduce',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  // Never reused: a server already on either port fails the run instead of being tested.
  webServer: [
    {
      // Started as scripts/dev.mjs starts it, minus --reload. The keyword provider is pinned
      // because pydantic-settings would otherwise pick up a real key from backend/.env.
      command: `uv sync --quiet && exec .venv/bin/uvicorn catalogue.app:create_app --factory --port ${String(apiPort)} --log-level warning`,
      cwd: '../backend',
      url: `${apiUrl}/health`,
      env: {
        CATALOGUE_CURATION_PROVIDER: 'keyword',
        CATALOGUE_KEYWORD_DELAY_MS: '0',
        CATALOGUE_CORS_ORIGINS: JSON.stringify([webUrl]),
        // Every test creates from this one address, so the default of 10 a minute would throttle
        // the suite.
        CATALOGUE_CREATE_RATE_LIMIT_PER_MINUTE: '1000',
      },
      reuseExistingServer: false,
    },
    {
      // The production build, so E2E exercises what ships, compiled by React Compiler.
      command: `pnpm exec vite build && pnpm exec vite preview --port ${String(webPort)} --strictPort`,
      url: webUrl,
      env: { VITE_API_BASE_URL: apiUrl },
      reuseExistingServer: false,
    },
  ],
})
