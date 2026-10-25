import babel from '@rolldown/plugin-babel'
import tailwindcss from '@tailwindcss/vite'
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import { playwright } from '@vitest/browser-playwright'
import { msw } from 'msw/vite'
import { defineConfig } from 'vitest/config'

export default defineConfig(({ mode }) => ({
  plugins: [
    react(),
    // Off under test: the compiler's memo-cache branches would count against the branch-coverage gate.
    mode !== 'test' && babel({ presets: [reactCompilerPreset()] }),
    tailwindcss(),
    mode === 'test' && msw({ mode: 'worker-only' }),
  ],
  resolve: { tsconfigPaths: true },
  server: { port: 5173, strictPort: true },
  preview: { port: 4173, strictPort: true },
  test: {
    // Vitest's own server inherits server.strictPort, which stops a second run from starting while one is open.
    api: { strictPort: false },
    setupFiles: ['src/test/setup.ts'],
    browser: {
      enabled: true,
      provider: playwright(),
      headless: true,
      instances: [{ browser: 'chromium' }],
    },
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        'src/**/*.gen.ts',
        'src/main.tsx',
        'src/**/*.d.ts',
      ],
      thresholds: { lines: 95, branches: 95, functions: 95, statements: 95 },
    },
  },
}))
