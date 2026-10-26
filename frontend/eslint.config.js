import js from '@eslint/js'
import eslintReact from '@eslint-react/eslint-plugin'
import pluginQuery from '@tanstack/eslint-plugin-query'
import vitest from '@vitest/eslint-plugin'
import prettier from 'eslint-config-prettier/flat'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import playwright from 'eslint-plugin-playwright'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default defineConfig(
  globalIgnores(['dist', 'coverage', 'playwright-report', 'test-results', 'src/**/*.gen.ts']),
  {
    files: ['**/*.{js,ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.strictTypeChecked,
      tseslint.configs.stylisticTypeChecked,
    ],
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  {
    files: ['src/**/*.{ts,tsx}'],
    extends: [
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      jsxA11y.flatConfigs.strict,
      eslintReact.configs['recommended-type-checked'],
      pluginQuery.configs['flat/recommended'],
    ],
    languageOptions: { globals: globals.browser },
    rules: {
      // react-hooks owns the hooks and compiler rules; these copies would report each problem twice.
      '@eslint-react/error-boundaries': 'off',
      '@eslint-react/exhaustive-deps': 'off',
      '@eslint-react/purity': 'off',
      '@eslint-react/rules-of-hooks': 'off',
      '@eslint-react/set-state-in-effect': 'off',
      '@eslint-react/set-state-in-render': 'off',
      '@eslint-react/static-components': 'off',
      '@eslint-react/unsupported-syntax': 'off',
      '@eslint-react/use-memo': 'off',
    },
  },
  { files: ['*.{js,ts}'], languageOptions: { globals: globals.node } },
  {
    files: ['src/**/*.test.{ts,tsx}'],
    extends: [vitest.configs.recommended],
    rules: {
      'vitest/expect-expect': [
        'error',
        { assertFunctionNames: ['expect', 'expectNoA11yViolations'] },
      ],
    },
  },
  {
    files: ['e2e/**/*.ts'],
    extends: [playwright.configs['flat/recommended']],
    rules: {
      'playwright/expect-expect': ['error', { assertFunctionNames: ['expectNoAxeViolations'] }],
    },
  },
  prettier,
)
