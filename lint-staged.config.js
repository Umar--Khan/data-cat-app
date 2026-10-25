/** @type {import('lint-staged').Configuration} */
export default {
  // --no-warn-ignored: a staged file that ESLint ignores (schema.gen.ts) would otherwise warn, and --max-warnings=0 turns that into a failure.
  'frontend/**/*.{ts,tsx}': [
    'pnpm --dir frontend exec eslint --fix --max-warnings=0 --no-warn-ignored',
    'prettier --write',
  ],
  '*.{js,mjs,cjs,css,md,json,yml,yaml,html}': 'prettier --write',
  'backend/**/*.py': [
    'uv run --directory backend ruff check --fix',
    'uv run --directory backend ruff format',
  ],
}
