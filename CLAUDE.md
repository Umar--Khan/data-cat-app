# Data catalogue

A take-home data catalogue: a FastAPI service and a React single-page app in one pnpm workspace. Users register a dataset (name, owner, description). `POST /datasets` curates it into tags and a one-sentence summary, with Claude when `ANTHROPIC_API_KEY` is set and a deterministic keyword curator otherwise, and stores it in process memory. A failed curation never loses the record: it is saved with `curation.status: "failed"`.

**Stack:** Python 3.14 via uv · FastAPI · Pydantic · Anthropic SDK · React 19 · Vite 8 · TypeScript 6 · Tailwind CSS 4 · TanStack Query · Vitest Browser Mode · Playwright.

## Layout

```
backend/     FastAPI app (uv project, package src/catalogue) with its pytest and schemathesis suites
frontend/    React app with its Vitest and Playwright suites; generated API types in src/lib/api/
specs/       one behaviour contract per subsystem
docs/        architecture and the latest browser-verification report
scripts/     Node scripts behind the root commands: dev servers, OpenAPI codegen, env bootstrap
.github/     CI workflow and its shared setup action
.claude/     project settings, skills and agents for Claude Code
```

## Commands

Run from the repository root. Focused runs (one test, watch mode) are in `backend/CLAUDE.md` and `frontend/CLAUDE.md`.

| Command             | Does                                                                                                     |
| ------------------- | -------------------------------------------------------------------------------------------------------- |
| `pnpm bootstrap`    | Installs both workspaces and Playwright's Chromium; creates `backend/.env` from `.env.example` if absent |
| `pnpm dev`          | API on :8000 with reload, web on :5173                                                                   |
| `pnpm dev:degraded` | API on :8100 with every curation failing offline, web on :5180; runs beside `pnpm dev`                   |
| `pnpm check`        | `check:api`, then `check:web`. The pre-push hook runs it.                                                |
| `pnpm check:api`    | ruff, import-linter, mypy, pytest with the 95 % coverage gate, OpenAPI drift check                       |
| `pnpm check:web`    | ESLint, Prettier check, `tsc -b`, Vitest with the 95 % coverage gate                                     |
| `pnpm test:e2e`     | Playwright against the production build, on its own servers (API :8001, preview :4173)                   |
| `pnpm verify:api`   | The brief's API checklist against a fresh server on a free port; `--degraded`, `--provider anthropic`    |
| `pnpm gen:api`      | Exports OpenAPI to `frontend/openapi.json` and regenerates `frontend/src/lib/api/schema.gen.ts`          |
| `pnpm format`       | Prettier, then ruff fix and format                                                                       |

## Where truth lives

- `docs/architecture.md`: system view, layers, configuration, cross-cutting decisions.
- `specs/README.md`, then `specs/<name>.md`: one behaviour contract per subsystem, with its invariants and decided points.
- `backend/CLAUDE.md` and `frontend/CLAUDE.md`: conventions for each side, loaded when you work there.
- `docs/verification.md`: the latest Claude-in-Chrome verification report.
- Package versions live in the lockfiles, not in docs.

## Rules that hold everywhere

- Read a subsystem's spec before changing it. When a change alters behaviour the spec pins, update the spec in the same commit.
- Comments and docstrings say why, never what. No commented-out code, no TODOs.
- No test-only endpoints or flags.
- Tests never call the real Anthropic API.
- `frontend/openapi.json` and `schema.gen.ts` change only through `pnpm gen:api`. The drift check in `pnpm check:api` fails if they differ from the backend's OpenAPI document.
- Conventional Commits, enforced by commitlint and authored by the repository owner. No AI attribution in commits or PR descriptions; `.claude/settings.json` turns Claude Code's off.
- Plans and working notes go under `.claude/plans/`, which is git-ignored.
- `README.txt`, the original brief, is local-only and git-ignored. Never commit it; tracked files take only the seed data and test payload from it.
