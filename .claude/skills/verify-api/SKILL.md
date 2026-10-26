---
name: verify-api
description: Run the brief's API checklist against freshly started backend servers, in keyword and degraded modes, plus one live Claude run when a key is configured.
disable-model-invocation: true
---

# Verify the API

Run this after changing backend behaviour (routes, validation, problem details, curation) and before committing the change. Each command starts its own server on a free port, runs checks 1–6 from `specs/quality-gates.md` (Live API verification) and stops the server, so a running `pnpm dev` is never touched.

From the repository root, in order:

1. `pnpm verify:api` runs the keyword provider.
2. `pnpm verify:api --degraded` runs the offline failure configuration. Check 2 expects the record saved with a failed curation.
3. `pnpm verify:api --provider anthropic` makes one billed Claude call. Run it once and never repeat it to retry. If it stops before starting a server with "needs ANTHROPIC_API_KEY", no key is configured: report the live run as SKIPPED. Never open, read or print `backend/.env`.

## Reading the output

- One `PASS` or `FAIL` line per check. A `FAIL` line ends with the reason: the status, header or field that differed, with the start of the body when the status was wrong.
- Timestamped lines are the server's log. The first names the provider, model and host. A failed curation logs `Curation by <provider> failed as <failure>` with its cause at WARNING, or `failed unexpectedly` with a traceback at ERROR. A 500 logs a traceback.
- With `--provider anthropic`, check 2 is followed by the tags, summary and client-side latency. A successful call also logs an INFO line with the serving model, token usage and request id.
- A message before any check (server exited, no `/health` answer, wrong provider) is a startup failure. Read the server output above it.
- Exit code 0 means all six passed, 1 means a check or startup failed, 130 means interrupted.

## When a check fails

- Fix the code, never the expectations in `backend/scripts/verify_api.py`. Each check restates the brief or `specs/api-contract.md`.
- If only the live check 2 fails, as `misconfigured` or `unavailable`, the cause is the key, the account or the network. Report Anthropic's message and the request id from the log instead of changing code. A 400 saying the key is not scoped to a workspace means `ANTHROPIC_WORKSPACE_ID` must be set. `refused`, `invalid_output` and `failed unexpectedly` point at the prompt, the provider or the normaliser: fix those.
- After a fix, rerun the keyword and degraded modes. Ask before another live run.

## Report

One line per mode: PASS (6 of 6), FAIL with the failing checks and their reasons, or SKIPPED. For the live run, add the tags, summary, latency and the serving model.
