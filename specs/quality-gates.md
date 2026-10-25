# Quality gates

> _Draft_ · Last verified against code: not yet

## Purpose

What each test layer proves, the thresholds that fail a change, what the git hooks and CI run, how the Playwright harness keeps an in-memory backend predictable, and how Claude in Chrome verifies the running app. Every gate is defined once, as a root script, and the hooks and CI call those same scripts.

## Key files

- `package.json` (root scripts), `scripts/dev.mjs`, `.husky/`, `lint-staged.config.js`, `commitlint.config.js`, `prettier.config.js`, `.prettierignore`, `.nvmrc`.
- `.github/workflows/ci.yml`, `.github/actions/setup/action.yml`.
- `frontend/vite.config.ts` (Vitest and coverage), `frontend/eslint.config.js`, `frontend/playwright.config.ts`, `frontend/e2e/`, `frontend/src/test/`.
- `backend/pyproject.toml` (pytest, coverage, ruff, mypy, import-linter), `backend/tests/`, `backend/scripts/verify_api.py`.
- `.claude/skills/verify-ui/`, `.claude/skills/verify-api/`, `.claude/agents/ui-tester.md`, `.claude/agents/spec-auditor.md`, `docs/verification.md`.

## Behaviour contract

### Root scripts

| Script | Does |
|---|---|
| `pnpm bootstrap` | `pnpm install`, `uv sync` for the backend, installs Playwright's Chromium, and copies `backend/.env.example` to `backend/.env` if it is missing |
| `pnpm dev` | API on :8000 (auto-reload) and Vite on :5173. Prints the active curation provider from `/health`. |
| `pnpm dev:degraded` | API on :8100 with the offline failure configuration ([curation.md](./curation.md#provider-selection)) and `CATALOGUE_CORS_ORIGINS=["http://localhost:5180"]`; Vite on :5180 with `VITE_API_BASE_URL=http://localhost:8100`. Runs alongside `pnpm dev`. |
| `pnpm check` | `check:api`, then `check:web`. Pre-push runs this. |
| `pnpm check:api` | ruff (lint and format check), import-linter, mypy, pytest with coverage, and the OpenAPI drift check (regenerate to a temporary directory and compare with the committed files) |
| `pnpm check:web` | ESLint, `prettier --check .`, `tsc -b` (app, node configs, e2e), Vitest with coverage |
| `pnpm test:e2e` | Playwright |
| `pnpm verify:api` | `verify_api.py` against a freshly started server. Flags: `--degraded`, `--provider anthropic`. |
| `pnpm gen:api` | Exports OpenAPI and regenerates `schema.gen.ts` ([api-contract.md](./api-contract.md#invariants--decided-points)) |
| `pnpm format` | Prettier, then ruff fix and format |

The name is `bootstrap`, not `setup`, because on pnpm 9 and 10 `pnpm setup` runs pnpm's built-in command, which edits the shell profile and installs nothing. Focused runs (one test file, watch mode) use `uv run pytest …` and `pnpm --filter frontend exec vitest …` directly; `backend/CLAUDE.md` and `frontend/CLAUDE.md` list them.

### Git hooks (husky)

| Hook | Runs | Why there |
|---|---|---|
| `pre-commit` | lint-staged: ESLint `--fix` and Prettier on staged TS and TSX; Prettier on JS, CSS, MD, JSON and YAML; ruff fix and format on staged Python | Per-file and auto-fixing only, so it stays at a few seconds |
| `commit-msg` | commitlint with `config-conventional` | Conventional Commits |
| `pre-push` | `pnpm check` | Whole-program checks are too slow for every commit: `tsc`, `mypy`, import contracts, full suites with coverage, OpenAPI drift. A passing push equals CI minus the production build and E2E. |

### CI (GitHub Actions)

Three jobs run in parallel on pushes to `main` and on pull requests. A composite setup action installs pnpm (version from `packageManager`), Node (from `.nvmrc`) and uv, with caches. `UV_LOCKED=1` fails the run on a stale lockfile.

| Job | Steps |
|---|---|
| `backend` | `pnpm check:api` |
| `frontend` | Install Chromium (headless shell); `pnpm check:web`; production build |
| `e2e` | Install Chromium; `pnpm verify:api`; `pnpm verify:api --degraded`; `pnpm test:e2e`. On failure, upload the Playwright report. |

### Coverage gates

- **Frontend:** 95 % on lines, branches, functions and statements. `coverage.include` is `src/**/*.{ts,tsx}`, so files that no test imports still count, as 0 %. Every exclusion has a reason:
  - test files and `src/test/**`: test code;
  - `src/**/*.gen.ts`: generated types, protected by the drift check;
  - `src/main.tsx`: bootstrap only, run by every E2E test;
  - `*.d.ts`: declarations.
- **Backend:** 95 % on lines plus branches for `catalogue`, set as `fail_under` in `[tool.coverage.report]`. `--cov` is passed only by `check:api`, so focused runs are not failed by the gate.

### Test layers

| Layer | Runs in | Covers |
|---|---|---|
| Backend unit | pytest (anyio plugin for async) | `DatasetService`, the repository, both providers, the normaliser, the prompt, provider selection |
| Backend API | pytest + `TestClient` (httpx2), using `create_app(..., curation_provider=FakeCurationProvider())` | Every item on the brief's API checklist by name, every problem row, `Location`, camelCase, CORS on a 500 |
| Contract | schemathesis, loaded through a pytest fixture so it builds the app after the environment is isolated | For every documented operation: no 5xx, responses match the schema, every status returned is documented |
| Frontend | One Vitest Browser Mode project (Chromium), MSW 3 service worker, axe-core | Pure modules (`ApiError`, query keys, the zod schema against `openapi.json`, server-error mapping), and every component and hook in every state in [datasets-ui.md](./datasets-ui.md), with no axe violations in any state |
| E2E | Playwright | See below |

### E2E harness

- **Servers.** Playwright starts its own servers and never reuses one (`reuseExistingServer: false`), so a running `pnpm dev` holding a real key is never touched:
  - the API on :8001 with `CATALOGUE_CURATION_PROVIDER=keyword`, a keyword delay of 0, and `CATALOGUE_CORS_ORIGINS=["http://localhost:4173"]`;
  - the web app built with `VITE_API_BASE_URL=http://localhost:8001`, then served by `vite preview` on :4173.

  E2E therefore exercises the compiled production build.
- **Execution.** One worker, not fully parallel. `reducedMotion: 'reduce'`. One retry in CI. Traces and screenshots are kept on failure.
- **Isolation without a test-only endpoint.**
  - An `auto` fixture records the id of every `POST /datasets` 201 response (matched by path) and deletes those records through the public API in teardown, treating 404 as already cleaned.
  - Responses faked with `route.fulfill` use ids that cannot exist on the server (`fulfilled-1`).
  - Delete tests delete the record they created, never a seed. The literal `DELETE /datasets/1` is covered by pytest and `verify_api.py`.

  Every test therefore starts from the three seeds, and counts are deterministic.
- **Specs:**

| Spec | Proves |
|---|---|
| `checklist.spec.ts` | The brief's frontend checklist, one test per item: three seeds on load; the test payload adds a fourth entry with tags and summary (the POST is held by a route gate to assert the pending state); delete without a reload (a `window` sentinel survives, no navigation); an empty name or description shows inline errors, focuses the field and sends no POST |
| `failure-states.spec.ts` | API unreachable on load, then "Try again" recovers (`route.abort`); a POST answered with a curation-failed record shows the badge, the detail and the warning toast (`route.fulfill`); a delete returning 500 restores the row and shows an error toast |
| `keyboard.spec.ts` | Add and delete using only Tab, Shift+Tab, Enter, Space and Esc. Focus never lands on `body`, and focus after submit and after delete follows the spec. Tabs until the target's name matches, with a cap, rather than counting tab stops. |
| `a11y.spec.ts` | `@axe-core/playwright` (WCAG 2.2 A/AA plus best practice) on load, on the invalid form, after create once the toast has settled, on a failed-curation row, and with the dialog open. Plus a 320 × 720 viewport: no horizontal overflow, and the focused element visible. |

- **Axe and toasts.** Before scanning, wait for `[data-sonner-toast][data-mounted="true"]` at opacity 1. axe skips contrast checks on transparent elements, so a scan during the fade would pass without checking anything.

### Ports

| Context | API | Web |
|---|---|---|
| `pnpm dev` | 8000 | 5173 |
| `pnpm dev:degraded` | 8100 | 5180 |
| Playwright | 8001 | 4173 (preview) |
| `verify_api.py` | a free port | — |

### Live API verification

`backend/scripts/verify_api.py` starts uvicorn on a free port (keyword provider unless told otherwise), waits for `/health`, runs the brief's API checklist, prints one PASS/FAIL line per check, cleans up, and exits non-zero on any failure. The checks:

1. The three seeds are listed.
2. The test payload returns 201 with `Location`, tags and summary. With `--degraded`: `tags: []`, `summary: null`, `status: "failed"` and a detail.
3. `DELETE /datasets/1` returns 200, and the record disappears.
4. Repeating it returns a 404 problem.
5. A missing name returns a 400 problem with a `name` field error.
6. A missing description returns the same, for `description`.

With `--provider anthropic` (a key is required), it also prints the curated tags and summary and the client-side latency. Token usage and the serving model appear in the server's INFO log.

### Claude in Chrome verification

**`/verify-ui`** is a skill, run in the `ui-tester` agent. It drives the running app in the user's Chrome:

1. **Preflight.** If nothing is listening on :8000 and :5173, it starts `pnpm dev` itself. If the servers are already running, it checks that `GET /datasets` returns exactly the three seeds, and asks for a restart if not. The provider from `/health` goes in the report header.
2. **The brief's frontend checklist.** The delete step removes only the record the run created.
3. **Keyboard-only pass,** with a screenshot at each focus stop.
4. **Accessibility spot checks:** landmarks, names, the live region, and reflow at 320 px. It reads back `innerWidth`, and falls back to 400 % zoom if the window cannot get that narrow.
5. **Real failure states,** with no interception:
   - stop the API it started, load the page, restart the API, then "Try again";
   - delete a shown row with `curl`, then delete it in the UI (info toast).

   When the servers belong to the user, the stop-and-restart check is reported as SKIPPED.
6. **Console errors.**
7. **The degraded path,** against `pnpm dev:degraded`.

`ui-tester` returns its report as its final message: the date, the commit, a PASS/FAIL table, accessibility findings, and the path of any exported GIF. The invoking session writes it to `docs/verification.md`, with the GIF under `docs/verification/`. The committed report must be all PASS for the commit it names.

**Other tooling:**
- **`/verify-api`** (skill) runs `pnpm verify:api` and `pnpm verify:api --degraded`. With a key present it also runs `--provider anthropic`. When a check fails, it fixes the code, never the script's expectations.
- **`ui-tester`** (agent) uses `disallowedTools: Edit, Write, NotebookEdit` rather than a `tools` allowlist, so it keeps ToolSearch, which the deferred Chrome tools need. Bash stays available for starting servers, so not editing files is a rule in its prompt, not a hard guarantee.
- **`spec-auditor`** (agent) is read-only.
  - It compares `specs/`, `docs/architecture.md` and the CLAUDE.md files with the code.
  - It classifies each pinned statement as holds, invalidated or new-pin candidate, and proposes exact old→new edits.
  - Run it on request, and before any commit that changes pinned behaviour.
- **Python API conventions** live in `backend/CLAUDE.md`: layering, error handling, adding an operation end to end, testing. Claude Code loads the file when it works in `backend/`, so no separate authoring skill is needed.
- **Prerequisites:** Claude Code started with `--chrome` (or `/chrome` enabled), the Claude in Chrome extension connected, and a claude.ai login. These are developer tools. CI relies on Playwright.

## Invariants & decided points

- **No test-only endpoints or flags.** The keyword delay is a dev-experience setting: default 0, set only in `.env.example`.
- **No test ever calls the real Anthropic API.** pytest isolates the environment and `.env` ([curation.md](./curation.md#invariants--decided-points)); Playwright and CI pin the keyword provider.
- **Generated files are excluded** from Prettier, lint-staged and ESLint, so `pnpm gen:api` output stays byte-identical to what is committed.
- **Unit and component tests run the code as written; E2E runs the compiled build.** React Compiler is off under Vitest because its memo-cache branches would distort branch coverage.
- **Vitest Browser Mode, not jsdom with Testing Library.** Real CSS makes axe contrast and focus checks meaningful, native `<dialog>` works (jsdom has no `showModal`), and Vitest's own matchers type-check cleanly. Rejected: jsdom with Testing Library; happy-dom, whose `fetch` sends CORS preflights that MSW does not answer.
- **Playwright: one worker, the production build, fresh servers on dedicated ports.** The in-memory catalogue is shared state, and these choices make results deterministic without a reset endpoint. Rejected: a test-only reset endpoint; parallel workers.
- **Lint stack.**
  - Frontend: typescript-eslint `strictTypeChecked` and `stylisticTypeChecked`; react-hooks (including the compiler rules); `@eslint-react`, which catches missing keys and other JSX mistakes the hooks plugin does not; jsx-a11y `strict`; the TanStack Query, Vitest and Playwright plugins; `eslint-config-prettier`.
  - Backend: ruff with a broad rule set that includes `ERA` (commented-out code) and excludes pydocstyle (`D`), so nothing pushes toward docstrings that restate signatures. `mypy --strict` with the Pydantic plugin and the `deprecated` error code enabled. pytest with `strict = true` and `filterwarnings = ["error"]`.
- **Conventional Commits,** enforced by commitlint in `commit-msg`.

## Fixture/mock semantics

- E2E failure states use `page.route` (`abort` or `fulfill`) because they test frontend behaviour. The real backend's degraded path is exercised by `verify_api.py --degraded` in CI and by `/verify-ui` against `pnpm dev:degraded`.

## Deferred / open

- Firefox and WebKit projects are omitted: about 300 MB of downloads for one page of standard CSS. Each is a one-line addition.
- Whether a forked skill can use the Claude in Chrome tools is unverified. If it cannot, `/verify-ui` runs inline with the same steps.
