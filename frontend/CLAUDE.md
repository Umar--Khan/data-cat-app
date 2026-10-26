# Frontend

React 19 single-page app for the data catalogue: a form that registers a dataset, and below it the list of curated datasets with a delete action, over the FastAPI backend. Vite 8, TypeScript 6, Tailwind CSS 4. Run everything below from `frontend/`.

## Where truth lives

- `specs/datasets-ui.md`: copy, every state, focus rules, the accessibility contract, accessible names.
- `specs/styling.md`: design principles and tokens.
- `specs/api-contract.md`: the API this app consumes.
- `specs/quality-gates.md`: test layers, coverage, the lint stack.
- `docs/architecture.md`: structure, data flow, toolchain decisions.

Read the spec before changing behaviour it pins. Update it in the same commit as the code.

## Structure

```
src/app/                 page shell, providers, query client, error boundary
src/components/ui/       feature-agnostic primitives
src/features/datasets/   api/, hooks/, components/
src/lib/                 API client and ApiError, form helpers, env
src/test/                test setup, render helpers, axe and focus-ring helpers, media emulation, MSW
e2e/                     Playwright specs; fixtures.ts holds the cleanup fixture, route gates, keyboard, axe and toast helpers; urls.ts the dedicated ports
```

- Dependencies point one way: `features` may import `components/ui` and `lib`, and neither of those imports `features`.
- No router, no client-state store, no barrel files. kebab-case file names, named exports, `@/` for imports across folders.
- Tests sit next to the code they cover, as `*.test.ts` or `*.test.tsx`.

## Data

- Components get server data only through the feature hooks: `useDatasets`, `useCreateDataset`, `useDeleteDataset`. They never call the API client or `fetch`.
- `datasetsApi` is the only module that calls the client. Query and mutation keys come from the key factory. TanStack Query owns all server state.
- `src/lib/env.ts` is the only reader of `VITE_*` variables. A new one needs a declaration in `vite-env.d.ts` and a field in the env schema.
- Schemas use `import * as z from 'zod/mini'`, with checks passed to `.check()`. ESLint refuses `zod` itself, whose classic API adds about 60 kB to the bundle. `env.ts` loads zod's English locale, which then applies to every schema.
- Never edit `src/lib/api/schema.gen.ts` or `openapi.json`. After a backend contract change, run `pnpm gen:api` from the repository root and commit both files.

## Styling

- Semantic tokens only (`bg-surface`, `text-fg-muted`), defined in `@theme` in `src/index.css`. The default palette, radii and shadows are removed, so a raw class such as `bg-blue-500` silently emits no CSS. A token changes in `specs/styling.md` and `index.css` together.
- Each primitive has one `tv()`. A caller's `className` goes through `tv`'s `class` slot. Ad-hoc composition uses `cn` from tailwind-variants.
- Motion is colour and opacity only, 150 ms or less, behind `motion-safe:`. The pending spinner's rotation is the one exception, also behind `motion-safe:`. Never remove the global focus ring.

## Accessibility

- Every control has a visible `<label htmlFor>`. Hints and errors are linked through `aria-describedby`. `aria-invalid="true"` is set only while there is an error.
- Native elements first: `button`, `label`, `ul`, `dl`, and `<dialog>` with `showModal()` for confirmation. No `window.confirm`, no component library, no positive `tabIndex`.
- Focus moves are specified: the first invalid field after a failed submit, Name after a create unless focus has left the form, the neighbouring row's heading after a delete (the "Datasets" heading when none is left), the "Datasets" heading after Try again and from the skip link, and the fallback's heading when the page fails to render. A pending button uses `aria-disabled`, not `disabled`, so it keeps focus.
- Live regions are mounted before their text changes. `role="alert"` is only for errors that follow a user action.
- Accessible names are contract, listed in `specs/datasets-ui.md`. Tests, Playwright and `/verify-ui` select by them, so renaming one is a spec change.

## Testing

- Vitest Browser Mode in headless Chromium, with the real stylesheet loaded. Install the browser once with `pnpm exec playwright install chromium`.
- `render` from `vitest-browser-react`; `page` and `userEvent` from `vitest/browser`. Select by role and accessible name.
- Always `await expect.element(...)`. It retries until the timeout, and Vitest 5 fails a test that leaves one unawaited.
- Call `expectNoA11yViolations()` from `src/test/a11y.ts` (axe, WCAG 2.2 A and AA) in every state a test renders.
- MSW is v3: the unhandled-request option is `onUnhandledFrame`. `.env.test` points the API at `http://api.test`, which never resolves, and an API request no handler matches is answered at once with a 500 and a console error naming it, so it can never reach a running server.
- Render anything that uses the query client or toasts with `renderWithProviders` or `renderHookWithProviders` from `src/test/render.tsx`: a fresh client per test, the app's retry policy without the backoff, and a Toaster.
- Spy on module exports with `vi.mock(path, { spy: true })`. `vi.spyOn` cannot patch an ESM namespace.
- React Compiler is off under test, so coverage measures the code as written. Playwright runs the compiled production build.
- Coverage is gated at 95 % for lines, branches, functions and statements. Every file under `src/` counts, imported by a test or not, except the exclusions in `vite.config.ts`.

## Commands

| Purpose                              | Command                                     |
| ------------------------------------ | ------------------------------------------- |
| One test file                        | `pnpm exec vitest run src/app/app.test.tsx` |
| Watch                                | `pnpm test:watch`                           |
| Suite with the coverage gate         | `pnpm test`                                 |
| Lint                                 | `pnpm lint`                                 |
| Types                                | `pnpm typecheck`                            |
| Dev server on :5173                  | `pnpm dev`                                  |
| Production build, preview on :4173   | `pnpm build && pnpm preview`                |
| E2E against the production build     | `pnpm test:e2e`                             |
| One E2E spec (file name filter)      | `pnpm exec playwright test keyboard`        |
| Regenerate API types (from the root) | `pnpm gen:api`                              |

`pnpm dev` at the repository root starts the API and this app together. `pnpm check:web` there runs ESLint, Prettier, `tsc -b` and the tests with coverage.
