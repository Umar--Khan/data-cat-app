# API contract

> Last verified against code: 2026-10-26

## Purpose

The HTTP interface between the React app and the FastAPI backend: the brief's three endpoints plus a health check. This spec pins paths, status codes, payload shapes, error bodies and validation, and how the TypeScript types are generated from the backend's OpenAPI document.

## Key files

- `backend/src/catalogue/api/routes/datasets.py`, `routes/health.py`: the operations.
- `backend/src/catalogue/api/schemas.py`: wire models, the camelCase base model, the character rules. The length limits are constants in `backend/src/catalogue/domain/models.py`, which `NewDataset` also checks.
- `backend/src/catalogue/api/problems.py`: problem+json handlers, the 405 `Allow` rebuild, the unhandled-error middleware.
- `backend/src/catalogue/api/limits.py`: the body size middleware and the token-bucket rate limiter; `api/deps.py` applies the limiter to `POST /datasets`.
- `backend/src/catalogue/api/openapi.py`: documents error bodies under `application/problem+json`.
- `backend/src/catalogue/app.py`: `export_openapi()`, the codegen entry point.
- `scripts/gen-api.mjs`: runs `catalogue-openapi` and openapi-typescript. `--check` regenerates into a temporary directory and compares bytes with the committed files.
- `frontend/openapi.json`, `frontend/src/lib/api/schema.gen.ts`: generated, committed, never edited by hand.
- `backend/tests/api/`, `backend/tests/contract/`: the tests that pin this spec.

## Behaviour contract

| Operation (operationId)                   | Success                                                                       | Errors                                                                                |
| ----------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `GET /datasets` (`listDatasets`)          | `200` with `Dataset[]` in insertion order (oldest first)                      | —                                                                                     |
| `POST /datasets` (`createDataset`)        | `201` with `Location: /datasets/{id}` and the stored `Dataset`                | `400` invalid or malformed body; `413` body over 32 KiB; `429` over the creation rate |
| `DELETE /datasets/{id}` (`deleteDataset`) | `200` with the deleted `Dataset`                                              | `404` unknown id                                                                      |
| `GET /health` (`getHealth`)               | `200` with `{ "status": "ok", "curationProvider": "anthropic" \| "keyword" }` | —                                                                                     |

- **Curation never changes the status code** ([curation.md](./curation.md#invariants--decided-points)).
- **Startup state.** Three seed records with ids `"1"`, `"2"` and `"3"`, the brief's tags and summaries, and `curation: { status: "completed", provider: "seed", detail: null }`. Their `createdAt` is the process start time.
- **Ids** are strings from a counter that continues after the seeds and is never reused: create gives `"4"`, delete `"4"`, create gives `"5"`.
- **`createdAt`** is taken after curation, immediately before `add()`. List order and `createdAt` therefore always agree, even when two POSTs overlap.
- **`Location`** is a relative reference, built from the delete route with `url_for`, so it carries any root path the app is served under (`uvicorn --root-path /catalogue` gives `/catalogue/datasets/{id}`). There is no `GET /datasets/{id}`, so following it returns `405` with `Allow: DELETE`.
- An unknown route returns `404`, and so does a known path with a trailing slash: Starlette's slash redirect is turned off, because it answers with a bare 307 to an absolute URL built from the `Host` header. An unsupported method returns `405` with an `Allow` header listing every method the path supports.
- **Restarting the process restores the startup state**, including the restarts `--reload` triggers. Storage is in memory.

### Request limits

They bound what one client can cost and how far it can degrade the service for others: each create can be a billed Claude call. They do not protect against distributed denial of service, which belongs at the edge, in a reverse proxy or CDN.

- **Body size.** At most 32 KiB (32,768 bytes). A larger `Content-Length` fails before any of the body is read, and a chunked body fails at the chunk that crosses the limit. Either way the answer is a `413` problem with CORS headers. The largest valid body, every field at its limit in astral-plane characters each JSON-escaped as a 12-byte surrogate pair, is under 27 KB. Only `POST /datasets` reads a body.
- **Creation rate.** `POST /datasets` is limited per client address by a token bucket holding `CATALOGUE_CREATE_RATE_LIMIT_PER_MINUTE` tokens (default 10), refilled continuously, so the burst equals the rate. Over the limit the answer is a `429` problem with `Retry-After`, the whole seconds until the next token, rounded up. The other operations are cheap and not limited.
  - The limit is checked after the body is read as JSON and before its fields are validated. A create with invalid fields therefore spends a token, while a malformed or oversized body is rejected before the check.
  - Concurrent Claude calls are capped separately, across all clients ([curation.md](./curation.md#claude-request)).
- **Client address.** The peer address uvicorn reports, without the port. Behind a reverse proxy that is the proxy, so every client would share one bucket unless uvicorn takes the address from the proxy's `X-Forwarded-For`. uvicorn does that only with `--proxy-headers` (on by default) and only for connections from an address in `--forwarded-allow-ips` (default `127.0.0.1` and `::1`), which must name the proxy. The app never reads `X-Forwarded-For` itself, because any client can send one. Requests with no peer address, as on a Unix socket, share one bucket.
- **Memory.** A bucket left alone for a minute is full again, which is the same as having none, so it is dropped. At most 10,000 addresses are tracked; past that the one seen longest ago is forgotten, which lets it burst again rather than turning new clients away.

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

- Lengths are counted in code points after trimming. Trimming is Python's `str.strip()`: Unicode whitespace, which includes U+001C–U+001F and U+0085 but not U+FEFF.
- **Visible text.** A value must contain at least one letter, digit, punctuation mark or symbol (Unicode categories L, N, P and S). Whitespace, combining marks on their own and invisible characters do not count, so a value made only of them is blank, with the same message as an empty one.
- **No control or format characters.** Control characters (Cc) and format characters (Cf: zero-width spaces and joiners, bidirectional controls, the byte-order mark, the soft hyphen) are rejected, except tab and line feed in `description`. A carriage return is rejected too, so a client sends line breaks as `\n`.
- Unknown fields are rejected, so a client sending `tags` or `id` is told those fields are not accepted.
- Stored values are the trimmed values.

### Problem details

Every non-2xx response is `application/problem+json`, with `type`, `title`, `status`, `detail`, `instance` and `errors` always present, with one exception: a CORS preflight the policy rejects (an unlisted origin, method or request header) gets `400 text/plain` from Starlette's `CORSMiddleware` before the app runs. A browser acts only on the missing CORS headers and never shows that body. `instance` is the request path percent-encoded as a URI reference (RFC 9457), while `detail` quotes it decoded:

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
| A query, path or header parameter fails validation (no operation has one that can today)             | 400    | `about:blank`                 | Bad Request            | `[]`; `detail` lists the locations, such as `query.limit`               |
| Unknown dataset id                                                                                   | 404    | `/problems/dataset-not-found` | Dataset not found      | `[]`; `detail` names the id                                             |
| Unknown route                                                                                        | 404    | `about:blank`                 | Not Found              | `[]`                                                                    |
| Unsupported method                                                                                   | 405    | `about:blank`                 | Method Not Allowed     | `[]`; complete `Allow` header                                           |
| Body over 32 KiB                                                                                     | 413    | `about:blank`                 | Content Too Large      | `[]`; `detail` states the limit in bytes                                |
| Over the creation rate                                                                               | 429    | `about:blank`                 | Too Many Requests      | `[]`; `Retry-After` header, and `detail` says how long to wait          |
| Unhandled exception                                                                                  | 500    | `about:blank`                 | Internal Server Error  | `[]`; generic `detail`, traceback in the log only, CORS headers present |

A `RequestValidationError` counts as **malformed** when any of its errors has type `json_invalid` or location `("body",)`. Otherwise, when every error is located in the body, each becomes one `errors[]` entry whose `field` is the rest of its location joined with dots: the camelCase body property (`"name"`, not `"body.name"`), or a path such as `"tags.0"` for a nested one. An error located anywhere else gives the generic 400 above. FastAPI's own `HTTPException(400)` for an undecodable body also counts as malformed; it is matched by its detail, so any other 400 keeps its own.

| Pydantic error                                      | `message`                                                    |
| --------------------------------------------------- | ------------------------------------------------------------ |
| `missing`                                           | This field is required.                                      |
| `string_too_short` (including blank after trimming) | This field must not be blank.                                |
| `blank` (no visible character)                      | This field must not be blank.                                |
| `control_character`                                 | This field must not contain control or invisible characters. |
| `string_too_long`                                   | This field must be at most {max} characters.                 |
| `string_type`                                       | This field must be a string.                                 |
| `extra_forbidden`                                   | This field is not allowed.                                   |
| anything else                                       | Pydantic's own message                                       |

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
- **The body limit is a middleware of the app's own**, also inside `CORSMiddleware`. It wraps `receive` and raises an `HTTPException(413)` while the route reads the body, so the problem handler renders it with CORS headers. Rejected: Starlette's `RequestBodyLimitMiddleware`, which answers in `text/plain`.
- **The rate limit is a dependency on the create route**, in `api/` because client identity and 429 are HTTP concerns. Rejected: a middleware over every route, when only creates cost anything.
- **Character rules live in the wire schema; length limits in the domain too.** The lengths bound what a curation costs, so `NewDataset` enforces them for every caller. Which characters a client may send is a question for the boundary. Format characters include the zero-width joiner and non-joiner, so an emoji sequence or Persian text that uses them is rejected; invisible differences between two names were judged the greater risk in a catalogue.
- **422 never appears.** `POST` and `DELETE` declare a `4XX` response of `ProblemDetails` alongside their explicit 400 or 404, which stops FastAPI documenting 422. There is no app-level `default` response, because it would make schemathesis's "every returned status is documented" check pass vacuously.
- **Error bodies are documented under `application/problem+json`**, the type they are sent with.
- **camelCase on the wire.** Python stays snake_case through Pydantic's alias generator.
- **POST is not idempotent.** Clients must not retry one that may have run, because each attempt runs curation again. A 413 or 429 stored nothing, and a 429 may be sent again after `Retry-After`.
- **Codegen.**
  - `pnpm gen:api` runs `export_openapi()`, which builds the app without reading `backend/.env` and with the keyword provider, and writes `frontend/openapi.json` atomically. openapi-typescript then writes `schema.gen.ts`.
  - Both files are committed, and both are excluded from Prettier and ESLint so the generated output stays byte-identical.
  - `pnpm check` regenerates them and fails on any difference.
- **The frontend zod schema mirrors the length limits**, counted in code points after trimming. A test compares the limits with `openapi.json` and includes an astral-plane case. The two sides differ at the edges, and the API decides:
  - JS `trim()` strips U+FEFF, which Python's `strip()` keeps and the API then rejects as a format character; `strip()` strips U+001C–U+001F and U+0085, which `trim()` keeps.
  - zod does not apply the character rules.

  A value the form accepts and the API rejects comes back as a field error, which the form shows inline on that field, so nothing typed is lost.

## Fixture/mock semantics

- Frontend MSW handlers implement this contract with payloads typed from `schema.gen.ts`, so contract drift fails `tsc`. The store and scenarios are described in [datasets-ui.md](./datasets-ui.md#fixturemock-semantics).
- Backend API tests inject a `FakeCurationProvider` that returns scripted drafts or raises scripted failures.
- Rate-limit tests inject a `RateLimiter` on a `ManualClock`, which moves only when the test advances it. Other API tests keep the default limit; the schemathesis fixture raises it, because every request it generates comes from one address. The Playwright API server raises it too ([quality-gates.md](./quality-gates.md#e2e-harness)).

## Deferred / open

- No update operation and no pagination.
- **HEAD is not supported.** `HEAD /datasets` and `HEAD /health` return `405`, with `Allow` listing the path's real methods. FastAPI's `APIRoute`, unlike Starlette's own `Route`, does not add HEAD to GET routes, while RFC 9110 expects a general-purpose server to support it. Nothing in the app, its tests or its tooling sends HEAD, and supporting it would take a hidden second route for every GET, or a middleware that runs GET and drops the body, to serve a method no client uses.
