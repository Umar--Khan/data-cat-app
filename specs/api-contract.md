# API contract

> _Draft_ · Last verified against code: not yet

## Purpose

The HTTP interface between the React app and the FastAPI backend: the brief's three endpoints plus a health check. This spec pins paths, status codes, payload shapes, error bodies and validation, and how the TypeScript types are generated from the backend's OpenAPI document.

## Key files

- `backend/src/catalogue/api/routes/datasets.py`, `routes/health.py`: the operations.
- `backend/src/catalogue/api/schemas.py`: wire models, the camelCase base model, field limits.
- `backend/src/catalogue/api/problems.py`: problem+json handlers, the 405 `Allow` rebuild, the unhandled-error middleware.
- `backend/src/catalogue/api/openapi.py`: documents error bodies under `application/problem+json`.
- `backend/src/catalogue/app.py`: `export_openapi()`, the codegen entry point.
- `scripts/gen-api.mjs`: runs `catalogue-openapi` and openapi-typescript. `--check` regenerates into a temporary directory and compares bytes with the committed files.
- `frontend/openapi.json`, `frontend/src/lib/api/schema.gen.ts`: generated, committed, never edited by hand.
- `backend/tests/api/`, `backend/tests/contract/`: the tests that pin this spec.

## Behaviour contract

| Operation (operationId)                   | Success                                                                       | Errors                          |
| ----------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------- |
| `GET /datasets` (`listDatasets`)          | `200` with `Dataset[]` in insertion order (oldest first)                      | —                               |
| `POST /datasets` (`createDataset`)        | `201` with `Location: /datasets/{id}` and the stored `Dataset`                | `400` invalid or malformed body |
| `DELETE /datasets/{id}` (`deleteDataset`) | `200` with the deleted `Dataset`                                              | `404` unknown id                |
| `GET /health` (`getHealth`)               | `200` with `{ "status": "ok", "curationProvider": "anthropic" \| "keyword" }` | —                               |

- **Curation never changes the status code** ([curation.md](./curation.md#invariants--decided-points)).
- **Startup state.** Three seed records with ids `"1"`, `"2"` and `"3"`, the brief's tags and summaries, and `curation: { status: "completed", provider: "seed", detail: null }`. Their `createdAt` is the process start time.
- **Ids** are strings from a counter that continues after the seeds and is never reused: create gives `"4"`, delete `"4"`, create gives `"5"`.
- **`createdAt`** is taken after curation, immediately before `add()`. List order and `createdAt` therefore always agree, even when two POSTs overlap.
- **`Location`** is a relative reference. There is no `GET /datasets/{id}`, so following it returns `405` with `Allow: DELETE`.
- An unknown route returns `404`, and so does a known path with a trailing slash: Starlette's slash redirect is turned off, because it answers with a bare 307 to an absolute URL built from the `Host` header. An unsupported method returns `405` with an `Allow` header listing every method the path supports.
- **Restarting the process restores the startup state**, including the restarts `--reload` triggers. Storage is in memory.

## Data contract

### Dataset

```json
{
  "id": "4",
  "name": "Trade Confirmations",
  "owner": "Middle Office",
  "description": "Daily export of confirmed trades including instrument type, counterparty, notional value, and settlement date.",
  "tags": ["trading", "finance", "settlements", "daily"],
  "summary": "A daily export of confirmed trades covering instrument type, counterparty, and notional value.",
  "curation": { "status": "completed", "provider": "keyword", "detail": null },
  "createdAt": "2026-10-25T09:30:00Z"
}
```

- Every field is always present. Nullable fields are `null`, never missing.
- `tags`: `string[]` with at most 6 entries. Empty only when curation failed.
- `summary`: `string | null`. `null` only when curation failed.
- `curation.status`: `"completed" | "failed"`.
- `curation.provider`: `"anthropic" | "keyword" | "seed"`. Says who produced the tags.
- `curation.detail`: `string | null`. A sentence safe to show users when the status is `failed`, otherwise `null`.
- `createdAt`: ISO 8601 in UTC with a `Z` suffix.

### DatasetCreate (POST body)

| Field         | Rule                                                     |
| ------------- | -------------------------------------------------------- |
| `name`        | string, surrounding whitespace trimmed, 1–120 characters |
| `owner`       | string, trimmed, 1–120 characters                        |
| `description` | string, trimmed, 1–2000 characters                       |

- Lengths are counted in code points after trimming.
- Unknown fields are rejected, so a client sending `tags` or `id` is told those fields are not accepted.
- Stored values are the trimmed values.

### Problem details

Every non-2xx response is `application/problem+json`, with `type`, `title`, `status`, `detail`, `instance` and `errors` always present. `instance` is the request path percent-encoded as a URI reference (RFC 9457), while `detail` quotes it decoded:

```json
{
  "type": "/problems/validation-error",
  "title": "Invalid request body",
  "status": 400,
  "detail": "The request body has invalid fields: name, description.",
  "instance": "/datasets",
  "errors": [
    { "field": "name", "message": "This field is required." },
    { "field": "description", "message": "This field is required." }
  ]
}
```

| Situation                                                                                            | Status | `type`                        | `title`                | `errors`                                                                |
| ---------------------------------------------------------------------------------------------------- | ------ | ----------------------------- | ---------------------- | ----------------------------------------------------------------------- |
| One or more fields fail validation                                                                   | 400    | `/problems/validation-error`  | Invalid request body   | One entry per field                                                     |
| Body is invalid JSON or not an object, is empty, has a non-JSON `Content-Type`, or cannot be decoded | 400    | `/problems/malformed-body`    | Malformed request body | `[]`                                                                    |
| Unknown dataset id                                                                                   | 404    | `/problems/dataset-not-found` | Dataset not found      | `[]`; `detail` names the id                                             |
| Unknown route                                                                                        | 404    | `about:blank`                 | Not Found              | `[]`                                                                    |
| Unsupported method                                                                                   | 405    | `about:blank`                 | Method Not Allowed     | `[]`; complete `Allow` header                                           |
| Unhandled exception                                                                                  | 500    | `about:blank`                 | Internal Server Error  | `[]`; generic `detail`, traceback in the log only, CORS headers present |

A `RequestValidationError` counts as **malformed** when any of its errors has type `json_invalid` or location `("body",)`. Otherwise each error becomes one `errors[]` entry with `field` set to `loc[1]`, the camelCase body property (`"name"`, not `"body.name"`). FastAPI's own `HTTPException(400)` for an undecodable body also counts as malformed.

| Pydantic error                                      | `message`                                    |
| --------------------------------------------------- | -------------------------------------------- |
| `missing`                                           | This field is required.                      |
| `string_too_short` (including blank after trimming) | This field must not be blank.                |
| `string_too_long`                                   | This field must be at most {max} characters. |
| `string_type`                                       | This field must be a string.                 |
| `extra_forbidden`                                   | This field is not allowed.                   |
| anything else                                       | Pydantic's own message                       |

## Invariants & decided points

- **No `/api/v1` prefix.** The paths match the brief's checklist literally.
- **`GET /datasets` returns a bare array.** That matches the brief's wording ("returns all entries"), and pagination is out of scope. Rejected: an `{ items }` wrapper kept for a pagination feature that does not exist.
- **`owner` is required.** Every seed and every row shows an owner, and an entry with no accountable owner has little value in a catalogue. Making it optional would make it nullable across the stack. The README notes that this is stricter than the brief's checklist, which only names a missing name or description.
- **`curation.provider` includes `seed`.** The three seeds were curated by hand, so labelling them `anthropic` or `keyword` would misreport where they came from. Rejected: a nullable `curation`.
- **No single-dataset GET.** `Location` still identifies the created resource, and a GET handler would go beyond the brief's scope. RFC 9110 does not require one.
- **Generated names are the contract.**
  - Schemas: `Dataset`, `Curation`, `DatasetCreate`, `Health`, `ProblemDetails`, `FieldError`.
  - Enums, declared as PEP 695 `type` aliases so that Pydantic emits named components: `CurationStatus`, `CurationProviderName` (`anthropic | keyword`), `CurationSource` (`anthropic | keyword | seed`).
  - The path parameter is `id`.

  Renaming any of these is a contract change.

- **Three framework overrides:**
  - `RequestValidationError` and FastAPI's body-parse `HTTPException(400)` both map to the 400 problems above. The brief requires 400; FastAPI defaults to 422.
  - A 405 rebuilds `Allow` from every route that matches the path. Starlette lists only the first route it matched, which breaks RFC 9110.
  - Unhandled exceptions are rendered by a pure-ASGI middleware inside `CORSMiddleware`. Starlette's own 500 handler runs outside all user middleware, so its response would reach the browser without CORS headers and look like a network failure.
- **422 never appears.** `POST` and `DELETE` declare a `4XX` response of `ProblemDetails` alongside their explicit 400 or 404, which stops FastAPI documenting 422. There is no app-level `default` response, because it would make schemathesis's "every returned status is documented" check pass vacuously.
- **Error bodies are documented under `application/problem+json`**, the type they are sent with.
- **camelCase on the wire.** Python stays snake_case through Pydantic's alias generator.
- **POST is not idempotent.** Clients must not retry it, because each attempt runs curation again.
- **Codegen.**
  - `pnpm gen:api` runs `export_openapi()`, which builds the app without reading `backend/.env` and with the keyword provider, and writes `frontend/openapi.json` atomically. openapi-typescript then writes `schema.gen.ts`.
  - Both files are committed, and both are excluded from Prettier and ESLint so the generated output stays byte-identical.
  - `pnpm check` regenerates them and fails on any difference.
- **Field limits are mirrored in the frontend zod schema** with the same semantics: code points after trimming. A test compares the limits with `openapi.json` and includes an astral-plane case.

## Fixture/mock semantics

- Frontend MSW handlers implement this contract with payloads typed from `schema.gen.ts`, so contract drift fails `tsc`. The store and scenarios are described in [datasets-ui.md](./datasets-ui.md#fixturemock-semantics).
- Backend API tests inject a `FakeCurationProvider` that returns scripted drafts or raises scripted failures.

## Deferred / open

- No update operation and no pagination.
