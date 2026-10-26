# Backend

FastAPI service for the data catalogue: `GET /datasets`, `POST /datasets`, `DELETE /datasets/{id}` and `GET /health`, over an in-memory store. `POST` curates each dataset into tags and a summary before storing it, with Claude when a key is configured and a keyword curator otherwise. Python 3.14 via uv; the package is `src/catalogue`. Run everything below from `backend/`.

## Where truth lives

- `specs/api-contract.md`: paths, status codes, payloads, problem+json, validation, codegen.
- `specs/curation.md`: provider selection, the Claude request, normalisation, failures, the keyword mock.
- `docs/architecture.md`: layers, dependency injection, configuration, cross-cutting decisions.
- `specs/quality-gates.md`: gates, coverage, test layers.

Read the spec before changing behaviour it pins. Update it in the same commit as the code.

## Layers

`app → api → services → curation | repositories → domain → core`

- A module imports only from layers below it. `curation` and `repositories` never import each other.
- Only `api` and `app` import FastAPI or Starlette. Only `curation` imports `anthropic`.
- Only `app.py` and `curation/factory.py` name concrete implementations. Everything else depends on protocols.
- Domain types are frozen, slotted dataclasses with no framework imports. Wire types subclass `CamelModel` in `api/schemas.py` and map from domain objects through `from_attributes`. Routes build domain inputs from validated bodies, so services never see a Pydantic wire model.
- The lifespan builds dependencies and yields them as `LifespanState`. `api/deps.py` is the only reader of that state.
- `uv run lint-imports` enforces the import rules. A broken contract means the design is wrong, not the contract.

## Adding or changing an operation

1. Wire schema on `CamelModel`. Response fields have no defaults, so every field is required in OpenAPI; nullable is `X | None`, never missing. Enums are PEP 695 `type` aliases so OpenAPI emits named components.
2. Domain type in `domain/`.
3. Service method in `services/`, `async def`.
4. Repository method if needed, in the protocol and the in-memory store. Repository methods never await internally; that is what keeps store operations atomic without a lock.
5. Domain error in `domain/`, mapped to a problem in `api/problems.py`.
6. Route handler, `async def`. Its name becomes the camelCase operationId, so renaming it is a contract change. Declare every error status in `responses=` with `ProblemDetails`.
7. Tests in `tests/api/` (behaviour, every problem row) and `tests/contract/`.
8. `pnpm gen:api`, and commit `frontend/openapi.json` and `schema.gen.ts` with the change.
9. Update `specs/api-contract.md` in the same commit.

## Errors

- Services and repositories raise domain errors. Only `api/` knows HTTP: never raise `HTTPException` outside it.
- Every non-2xx response is problem+json. Invalid bodies are 400, never 422.
- Curation failures are not errors. Providers raise `CurationError`, and `CurationService` turns every failure into a stored record with `curation.status: "failed"`. Its `curate` never raises and holds the only broad `except` that lets a request carry on; the unhandled-error middleware's catch-all only renders the 500 problem.
- `curation.detail` is shown to users: never SDK messages, status codes or request ids. Those go to the log.

## Configuration

- `core/config.py` `Settings` is the only reader of the environment and `.env`, and the only source of the Anthropic key, host and workspace.
- A new variable needs a `Settings` field, a line in `.env.example` with a comment above it and the assignment itself commented out when it holds the code default (a test fails if the line is missing), and a row in the architecture Configuration table.

## Testing

- Fakes over mocks. Tests pass fakes to `create_app(...)` and run the real lifespan with `with TestClient(app) as client`. No `dependency_overrides`.
- The Anthropic provider runs the real `AsyncAnthropic` over `httpx2.MockTransport`, injected through `http_client`.
- Tests never reach the network or `backend/.env`. The autouse fixture in `tests/conftest.py` clears `ANTHROPIC_*` and `CATALOGUE_*`, points `ANTHROPIC_BASE_URL` at a dead port and sets `Settings.model_config["env_file"]` to `None`.
- Build Settings with `_env_file=None`. Pass aliased fields by alias, as `ANTHROPIC_API_KEY=SecretStr("…")`: the mypy plugin rejects the field name and a plain `str`.
- Async tests use `@pytest.mark.anyio` (anyio's plugin, asyncio backend).
- Warnings are errors. Fix the cause rather than filtering it.
- Coverage is gated at 95 % line plus branch, and only `--cov` runs check it.

## Commands

| Purpose                      | Command                                                                            |
| ---------------------------- | ---------------------------------------------------------------------------------- |
| One test                     | `uv run pytest tests/api/test_health.py::test_health_reports_the_keyword_provider` |
| Suite with the coverage gate | `uv run pytest --cov`                                                              |
| Types                        | `uv run mypy`                                                                      |
| Lint and format              | `uv run ruff check --fix .` then `uv run ruff format .`                            |
| Import contracts             | `uv run lint-imports`                                                              |
| Run with reload              | `uv run uvicorn catalogue.app:create_app --factory --reload --reload-dir src`      |
| Export OpenAPI               | `uv run catalogue-openapi --output PATH`                                           |

`pnpm check:api` at the repository root runs all of these, plus the OpenAPI drift check. After changing routes, validation or curation, also run `pnpm verify:api` and `pnpm verify:api --degraded` from the root: the API checklist against a real server, at no cost.
