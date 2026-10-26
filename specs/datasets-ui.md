# Datasets page

> Last verified against code: 2026-10-26

## Purpose

The single page of the app: a form to register a dataset and, below it, the catalogue list with each entry's owner, curation status, tags, summary and a delete action. This spec pins what users see and can rely on, including copy, focus behaviour and the accessibility contract. Tests, Playwright and `/verify-ui` all drive the page through the accessible names listed here.

## Key files

- `frontend/src/app/app.tsx`: page shell, landmarks, skip link.
- `frontend/src/features/datasets/components/`: `dataset-form.tsx`, `dataset-form-schema.ts`, `dataset-list.tsx`, `dataset-card.tsx`, `tag-list.tsx`, `curation-badge.tsx`, `dataset-list-states.tsx`.
- `frontend/src/features/datasets/hooks/use-datasets.ts`: queries, mutations, optimistic delete.
- `frontend/src/features/datasets/api/`: `datasets-api.ts` and `query-keys.ts`.
- `frontend/src/lib/api/api-error.ts`, `frontend/src/lib/forms/apply-server-errors.ts`.
- `frontend/src/app/query-client.ts`: query and mutation defaults.
- `frontend/src/components/ui/confirm-dialog.tsx`.
- `frontend/src/app/providers.tsx`: the Toaster, focus expanding the stack, and the front toast's height copied for scroll padding.
- `frontend/src/app/error-boundary.tsx`: the render-failure fallback.
- `frontend/src/index.css`: `--toast-clearance` and the sonner overrides.

## Behaviour contract

### Page

- Skip link "Skip to datasets", visually hidden until focused. It moves focus to the "Datasets" heading, which keeps a scroll margin so its focus ring stays in view, and the next Tab reaches the first row's Delete button. Then a `<header>` with the `h1` "Data Catalogue" and a one-line description.
- `<main>` holds two `<section aria-labelledby>`: "Add a dataset" (`h2`) and "Datasets" (`h2`, focusable with `tabIndex={-1}`).
- `<title>Data Catalogue</title>`, `<html lang="en">`.

### Form

- **Fields.**
  - Name, Owner and Description, each with a visible `<label>`.
  - Description has the hint "What the data contains and how often it updates. Used to generate tags and a summary."
  - "All fields are required." appears once, above the fields. There are no placeholders and no asterisks.
  - Name and Owner set `autoComplete="off"`.
- **Submit button.** Reads "Add dataset". The section heading is "Add a dataset".
- **Validation.**
  - The `<form>` sets `noValidate`. Inputs keep native `required` so assistive technology announces them, but the browser's validation bubbles never run, so the inline messages below are the only validation UI.
  - Validation runs on submit, then on change once a submit has failed.
  - Messages: "Enter a name", "Enter an owner", "Enter a description", and "{Field} must be {max} characters or fewer".
  - Whitespace-only input is rejected.
  - Lengths count code points after trimming, as the API does.
  - There is no native `maxLength`, which would silently truncate pasted text.
- **Invalid submit.** No request is sent. Focus moves to the first invalid field. Each invalid field has `aria-invalid="true"` and its error text linked through `aria-describedby`.
- **While the POST is in flight:**
  - The submit button reads "Saving and curating…" with a spinner. It has `aria-disabled="true"`, not `disabled`, so focus stays on it. A second submit is ignored.
  - Inputs are `readOnly`.
  - An always-mounted `role="status"` line shows "Generating tags and a summary. This can take up to 20 seconds."
  - There is no client-side timeout, and the POST is never retried.
- **Success.** The form resets once `handleSubmit` has settled, so the next entry starts in the not-yet-submitted validation state. Focus moves to Name.
  - Curation completed: success toast `Added "{name}"`.
  - Curation failed: warning toast `Saved "{name}" without AI tags`, with `curation.detail` as its description.
  - The new row appears at the end of the list.
- **Server rejection.**
  - Field errors in a 400 response that match a form field are shown inline on those fields, and focus moves to the first of them in form order (Name, Owner, Description), whatever order the server lists them in.
  - Anything else shows an inline danger alert above the submit button (`role="alert"`), titled "Couldn't add the dataset", with the `ApiError` message as its body. That covers a 400 with no field error matching a form field, any other 4xx or 5xx, and network failures. The alert is cleared at the start of every submit, so a repeated failure is mounted, and announced, again.
  - Typed values are kept. When the rejection is shown as the alert, focus stays on the submit button.

### List

- **Order** is server order: oldest first, new rows appended.
- **Status region.** An always-mounted, screen-reader-only `role="status"` region announces "Loading datasets…", "Couldn't load datasets" when a load fails, and "Couldn't refresh. Showing the last loaded list." when a refresh fails. It is cleared while a retry runs, so a repeated failure is announced again.
- **Loading.** Three `aria-hidden` skeleton cards.
- **Empty.** "No datasets yet. Add one with the Add a dataset form."
- **Failed load, nothing on screen.** Danger alert "Couldn't load datasets" with the error message and a "Try again" button. The alert has no live role, because the status region announces it. Try again puts the list back into the loading state (skeleton, "Loading datasets…").
- **Failed background refresh, data still on screen.** The data stays, with a warning alert "Couldn't refresh. Showing the last loaded list." and "Try again", which shows pending while the retry runs. No live role, because the status region announces it.
- **Try again** moves focus to the "Datasets" heading, because the alert holding the button goes away when the retry starts (failed load) or succeeds (failed refresh).
- **Row.** An `<li>` containing an `<article aria-labelledby>` with:
  - the `h3` dataset name, focusable with `tabIndex={-1}`;
  - the owner, as a `<dl>` pair;
  - the curation badge;
  - the tags as `<ul aria-label="Tags">`, or "No tags" text, never an empty list;
  - the summary, or `curation.detail` when curation failed;
  - the Delete button.

### Curation badge

A lookup keyed by the generated `curation` unions, so a new enum value fails `tsc` after codegen:

| `curation`             | Badge             | Icon          |
| ---------------------- | ----------------- | ------------- |
| completed, `anthropic` | Curated by Claude | Sparkles      |
| completed, `keyword`   | Keyword curated   | Tag           |
| completed, `seed`      | Sample data       | Database      |
| failed (any provider)  | Curation failed   | TriangleAlert |

Every badge carries text. Colour and icon only reinforce it.

### Delete

1. The row's button shows "Delete", and its accessible name is "Delete {name}". The visible label starts the accessible name (WCAG 2.5.3).
2. It opens a native `<dialog role="alertdialog">`:
   - title `Delete "{name}"?`;
   - text "It will be removed from the catalogue. This can't be undone.";
   - buttons Cancel and "Delete dataset", in that order, with Cancel focused on open.
3. Esc or Cancel closes the dialog, and focus returns to the row's Delete button.
4. Confirm:
   - The focus target is chosen first: the next row's heading, else the previous row's, else the "Datasets" heading. When a refresh has already removed the row, it has no neighbours, so the target is the "Datasets" heading.
   - The dialog closes and the delete mutation starts. The row disappears at once, because pending deletes are filtered out of the list.
   - Focus moves to the target once the row has left the DOM. This happens exactly once, so later list changes never move focus.
5. The outcome is handled in the mutation's own callbacks, so it is reported even when deletes overlap:
   - **Success:** the row is removed from the list cache. Toast: `Deleted "{name}"`.
   - **404:** the row is removed from the list cache. Info toast: `"{name}" was already removed`.
   - **Any other failure:** the row reappears as soon as the mutation stops pending. Error toast: `Couldn't delete "{name}"`, with the message. The list refetches in the background, not awaited.

   Cache removals happen after `cancelQueries` and before the mutation stops pending, so the row never flashes back. A refresh that `cancelQueries` stopped is started again after the write, so a failed delete's background refetch is not lost to an overlapping success.

### Toasts

- sonner, bottom-right, at most three visible.
- The close button is enlarged to 24×24 px.
- Success and info toasts last 5 s. Warning and error toasts last 10 s and have a close button.
- Toasts pause on hover and focus, and Alt+T reaches the region. sonner pauses only while its stack is expanded, so focus inside the stack expands it; while the list Alt+T focuses holds focus, its toasts carry the focus ring, since the list has no height of its own.
- `html { scroll-padding-bottom }` keeps a focused element from scrolling underneath the toast stack, which matters on narrow screens where toasts are full width (WCAG 2.4.11). It is sized from the front toast's height as sonner measures it, so a long dataset name or enlarged text cannot outgrow it, and it never drops below 10rem, so the page's bottom padding holds still for short toasts. Toast text is never truncated. The page shell pads its bottom by the same `--toast-clearance`, because scroll padding cannot lift the last row's controls past the end of the page.

### Render failure

An error boundary at the root, outside the providers, replaces the page with a `<main>` holding the focused `h1` "Something went wrong", the text "The page hit an unexpected error. Reload it to carry on; saved datasets are not affected." and a "Reload page" button.

## Data contract

- **Types** come from `schema.gen.ts`: `Dataset`, `Curation`, `DatasetCreate`, `ProblemDetails`, `FieldError`.
- **`ApiError`** has `kind: 'http' | 'network'`, `status` (`null` when no response arrived), `message` and `fieldErrors`.
  - For problem responses (`application/problem+json` with a problem body), `message` is the problem's `detail`, falling back to its `title`. A body that does not match `ProblemDetails` (string `title` and `detail`, and `errors` whose entries each have a string `field` and `message`) is treated as a plain HTTP error.
  - Any other error response gets "The server returned an unexpected error (HTTP {status})."
  - A network failure (fetch's `TypeError`) gets "Could not reach the server. Check your connection and try again."
  - Abort errors, and any other thrown error, are passed through untouched.
- **Keys.** Query key `['datasets', 'list']`, holding `Dataset[]`. Mutation keys `['datasets', 'create']` and `['datasets', 'delete']`.
- **Query defaults:** `staleTime` 30 s; retry only network errors and 5xx, at most twice; `networkMode: 'always'`. The browser's online flag says nothing about a localhost API.
- **Mutation defaults:** `retry: false` (POST is not idempotent), `networkMode: 'always'`.

## Invariants & decided points

- **Accessible names are part of the contract**: Name, Owner, Description, Add dataset, Saving and curating…, Delete {name}, Delete dataset, Cancel, Try again, Skip to datasets, Reload page, plus sonner's own "Notifications alt+T" region and "Close toast" button. Tests, E2E specs and `/verify-ui` use these names, so a sonner upgrade that renames either is a spec change.
- **The "20 seconds" in the pending copy mirrors the default** of `CATALOGUE_ANTHROPIC_TIMEOUT_SECONDS`. A change to that default changes this copy in the same commit.
- **Create writes the server's record into the cache** after `cancelQueries`, and does not refetch beyond restarting a refresh it cancelled. The 201 body is the canonical record. Create and delete cancel only a list that has data: cancelling a first load reverts it to pending with no fetch left to settle it, so a first load in flight is left to finish.
- **Optimistic delete filters pending delete mutations out of the list in `select`.** Concurrent deletes cannot bring each other's rows back, and a failure restores its row without manual work. Rejected: snapshot and rollback in `onMutate`/`onError`, where one delete's rollback can restore another's row.
- **Delete is confirmed** (WCAG 2.2 SC 3.3.4, AA, requires deleting stored data to be confirmed, checked or reversible). Rejected: one-click delete, which fails AA; undo, which would need a restore endpoint or a delayed DELETE that is lost if the tab closes.
- **Native `<dialog>` with `showModal()`; no component library.** The dialog is the only non-trivial widget besides toasts. `showModal()` provides the top layer, an inert background, Esc and focus return. The dialog reports the closes it makes (Esc, Cancel, confirm) at once rather than through the `close` event, which arrives a task later and would leave a Delete pressed in between with nothing to reopen. A close it did not make, such as the browser handling Esc without a `cancel` event, is still reported through the `close` event, but only while `open` is true; closing it by setting `open` to false reports nothing. Rejected: Radix or shadcn, which would re-implement those behaviours in JavaScript.
- **react-hook-form with zod.** React 19 form actions and `useOptimistic` are not used. TanStack Query already owns pending and error state, and a second mechanism would be a second source of truth.
- **`role="alert"` only for errors that follow a user action.** Status regions are mounted before their text changes, because a live region inserted along with its content is not reliably announced.

### Accessibility contract (WCAG 2.2 AA)

| Area                                          | Commitment                                                                                                                                                                                                                               |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Structure (1.3.1, 2.4.1, 2.4.6)               | Landmarks; one `h1`, an `h2` per section, an `h3` per row, with no skipped levels; a real `<ul>` list; a skip link                                                                                                                       |
| Labels and errors (1.3.1, 3.3.1–3.3.3, 4.1.2) | `<label for>` on every control; native `required` with `noValidate` on the form; hint and error through `aria-describedby`; `aria-invalid` only when there is an error; error text names the fix; focus moves to the first invalid field |
| Status messages (4.1.3)                       | Toasts in a polite live region; always-mounted `role="status"` regions for pending, loading, load failure and refresh failure; each event announced once                                                                                 |
| Keyboard (2.1.1, 2.1.2, 2.4.3)                | Native controls only; no positive `tabindex`; the dialog is modal and closes on Esc; focus rules as above                                                                                                                                |
| Focus visible (2.4.7, 2.4.11, 1.4.11)         | A global `:focus-visible` ring of at least 3:1 on every background; toasts never hide the focused element                                                                                                                                |
| Target size (2.5.8)                           | Primary controls 40 px; row Delete and Try again 32 px; toast close 24 px                                                                                                                                                                |
| Colour (1.4.1, 1.4.3, 1.4.11)                 | Text on every status; token contrast as in [styling.md](./styling.md); controls keep a visible boundary in forced-colours mode                                                                                                           |
| Reflow and resize (1.4.4, 1.4.10, 1.4.12)     | One column; rem-based type; no fixed heights; works at 320 CSS px and 200 % zoom                                                                                                                                                         |
| Error prevention (3.3.4)                      | Delete is confirmed                                                                                                                                                                                                                      |
| Timing (2.2.1)                                | Toasts pause on hover and focus; their information also stays on the page (badge, restored row, inline alert)                                                                                                                            |
| Motion (2.3.3, AAA, adopted beyond AA)        | Animation only under `motion-safe`; sonner honours reduced motion                                                                                                                                                                        |

## Fixture/mock semantics

MSW (`frontend/src/test/msw/`) serves the API contract over a typed in-memory store, reset before each test and seeded with the three seed records (`store.reset(records)` starts a test from other records). `apiRequests()` lists the requests the mock API received in the current test. A request to the API that no handler matches is answered with a 500 and a console error naming it. Named scenarios, each lasting until the stop function it returns runs or the test ends:

- `listFails`, `createInvalid(fieldErrors)`, `createCurationFailed`, `deleteFails(id?)`, `deleteNotFound(id?)`;
- `hold(method)`, which returns a gate the test releases, so pending states can be asserted without timers. Each call holds one request; overlapping requests claim gates in call order, and a held request goes on to whichever handler answers it.

## Deferred / open

- Undo for delete. It would need a restore endpoint, which is outside the brief's scope.
