---
name: verify-ui
description: Verify the running data catalogue in the user's Chrome through Claude in Chrome — the brief's frontend checklist, a keyboard-only pass, accessibility spot checks, real failure states and the degraded path — and return a PASS/FAIL report.
context: fork
agent: ui-tester
argument-hint: '[keyword]'
---

# Verify the UI

Arguments: `$ARGUMENTS`. With `keyword`, servers this run starts use the keyword curator, so no step calls Claude. Without it they use whatever `backend/.env` configures; with a Claude key, each dataset this run creates there is one billed call: three in all (the checklist entry, the keyboard pass's entry and the deleted-elsewhere record).

The contract is `specs/datasets-ui.md` (copy, states, focus rules, accessible names) and `specs/quality-gates.md` (Claude in Chrome verification). The test payload is `TEST_PAYLOAD` in `backend/scripts/verify_api.py`; the seeds are in `backend/src/catalogue/repositories/seeds.py`.

## 1. Preflight

- Check both ports: `curl -sf http://127.0.0.1:8000/health` and `curl -sf -o /dev/null http://localhost:5173`.
- **Neither answers:** start the two servers yourself, as separate background processes, so step 5 can stop and restart the API alone. `pnpm dev` would stop the web server along with the API.
  - API, from `backend/`: `uv sync --quiet && exec .venv/bin/uvicorn catalogue.app:create_app --factory --port 8000`, with `CATALOGUE_CURATION_PROVIDER=keyword` in its environment when the argument is `keyword`.
  - Web, from the repository root: `pnpm --filter frontend exec vite --port 5173 --strictPort`.
  - Wait until both answer. Record that this run owns the servers.
- **Both answer:** the servers are the user's. `GET http://127.0.0.1:8000/datasets` must return exactly the three seeds; if not, stop and report that the catalogue needs a restart. The `keyword` argument cannot change a running server; say so in the header if it was given.
- **Only one answers:** stop and report which port is busy.
- Put `curationProvider` from `/health` in the report header.
- Open your tab, then call `read_console_messages` and `read_network_requests` once straight away: both record only from their first call, so steps 2 and 6 depend on it.

## 2. The brief's frontend checklist

Type with real key presses; don't set values through JavaScript.

1. **Seeds on load:** the three seed names as the row headings, in order.
2. **Inline errors:** submit the empty form. Each field shows its error from the spec, has `aria-invalid="true"` and an `aria-describedby` that includes the message; focus is on Name; no `POST /datasets` was sent (`read_network_requests`).
3. **The test payload adds a fourth entry:** fill and submit it. Read the pending state from the DOM in the same `browser_batch` as the click ("Saving and curating…", `aria-disabled`, read-only fields, the status text): with the keyword curator it lasts about a second, so a screenshot taken afterwards usually misses it, and the spinner may not be caught at all. Then: a fourth row with the payload's name and owner, tags and a one-sentence summary, the badge for the provider ("Keyword curated" or "Curated by Claude"), the success toast, an empty form and focus on Name. A "Curation failed" row here is a FAIL against the brief; quote its detail.
4. **Delete without a refresh:** before deleting, set `window.verifySentinel = 'same page'`. Open that row's dialog and check its copy and that Cancel has focus; press Esc and check nothing was deleted and focus returned to the row's Delete button. Reopen it and confirm. The row disappears, the sentinel survives, the success toast shows, focus moves to the neighbouring row's heading, and `GET /datasets` is back to the seeds. Delete only the record this run created.

## 3. Keyboard-only pass

Reload, then use only Tab, Shift+Tab, Enter, Space and Esc. Take a screenshot at each focus stop (`scale: 0.5`) and check the focus ring is visible on each. Start with the skip link ("Skip to datasets"): it must move focus to the Datasets heading. Add the test payload, then delete it through the dialog, checking focus after each step against the spec's focus rules. Focus must never land on `body` while `document.hasFocus()` is true. Tab past the dialog's last button moves focus to the browser's own UI, which is native `showModal()` behaviour: `activeElement` then reads `body` with `hasFocus()` false, and the next Tab returns to Cancel. That is not a failure.

## 4. Accessibility spot checks

- Landmarks: one `header`, one `main`, both sections labelled by their headings; one `h1`; heading levels in order.
- Names: every control's accessible name matches the spec's list. `read_page` lists only what is in the viewport and names a button by its first text node, so check names in the DOM: a row's Delete button is "Delete" plus the dataset name in visually hidden text.
- Live regions: the `role="status"` regions exist before their text changes.
- Reflow at 320 px: `resize_window` to 320 × 720, then read `innerWidth` in a new tab, since an open tab may keep its old size. If the window cannot get that narrow, check the narrowest width it reaches, and also load the app in a same-origin `<iframe>` 320 px wide added through `javascript_tool` (it changes no files). At each width, check `document.documentElement.scrollWidth <= clientWidth`, and, right after a confirmed delete so its toast is showing, that the last row's Delete button, focused, is not covered by the toast stack.

## 5. Real failure states, with no request interception

- **API down on load:** only when this run owns the servers. Stop the API process, reload the page, wait for "Couldn't load datasets", start the API again with the same command, then press "Try again": the seeds return and focus is on the Datasets heading. Otherwise SKIPPED, because the servers are the user's.
- **Deleted elsewhere:** create a record with `curl -X POST` (the test payload, renamed "Verify UI deleted elsewhere"), reload so it shows, delete it with `curl -X DELETE`, then delete it in the page: the info toast says it was already removed, and the row goes.

## 6. Console errors

`read_console_messages` with `onlyErrors: true` for the tab, after the steps above. Expected failed requests from step 5 are not errors; anything else is.

## 7. The degraded path

Start `pnpm dev:degraded` in the background (API :8100, web :5180) unless something already answers on those ports. In a tab at `http://localhost:5180`, submit the test payload: the row shows the "Curation failed" badge and the failure detail instead of tags and summary, and the warning toast `Saved "Trade Confirmations" without AI tags` shows the detail as its description, with a close button. Delete the row. Stop `pnpm dev:degraded` if you started it.

## Finish

Close every tab in your group, including the one `tabs_context_mcp` opened, stop every process you started, confirm `GET /datasets` on :8000 returns only the seeds if the servers are the user's, and return the report in the format your agent definition gives.
