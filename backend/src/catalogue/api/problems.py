import logging
from collections.abc import Callable, Coroutine, Mapping, Sequence
from http import HTTPMethod, HTTPStatus
from typing import Any, Final
from urllib.parse import quote

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.routing import Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from catalogue.api.schemas import FieldError, ProblemDetails
from catalogue.domain.errors import DatasetNotFoundError

logger = logging.getLogger(__name__)

PROBLEM_MEDIA_TYPE: Final = "application/problem+json"

type ExceptionHandler = Callable[[Request, Any], Coroutine[Any, Any, Response]]

_MESSAGES: Final[Mapping[str, str]] = {
    "missing": "This field is required.",
    "string_too_short": "This field must not be blank.",
    "string_type": "This field must be a string.",
    "extra_forbidden": "This field is not allowed.",
}
# FastAPI's detail for a body it read but could not decode. Matching it, rather than every 400,
# keeps any other 400 from being reported as a malformed body.
_BODY_PARSE_FAILED: Final = "There was an error parsing the body"


def exception_handlers() -> dict[int | type[Exception], ExceptionHandler]:
    """Handlers that turn validation, routing and domain errors into problems."""
    return {
        RequestValidationError: _invalid_body,
        HTTPException: _http_error,
        DatasetNotFoundError: _dataset_not_found,
    }


class UnhandledErrorMiddleware:
    """Renders an unhandled exception as a 500 problem, with the traceback in the log only.

    It must be installed inside CORSMiddleware. Starlette's own 500 handler runs outside every
    user middleware, so its response would reach the browser without CORS headers and look like a
    network failure instead of a server error.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def send_and_track(message: Message) -> None:
            nonlocal response_started
            response_started = response_started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, receive, send_and_track)
        except Exception:
            # A second response cannot follow one that has started, so the server has to see
            # the error and drop the connection.
            if response_started:
                raise
            logger.exception("Unhandled error in %s %s", scope["method"], scope["path"])
            response = _about_blank(
                scope["path"],
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "The server hit an unexpected error.",
            )
            await response(scope, receive, send)


async def _invalid_body(request: Request, error: RequestValidationError) -> JSONResponse:
    errors: Sequence[Mapping[str, Any]] = error.errors()
    if any(_is_malformed(entry) for entry in errors):
        return _malformed_body(request)
    # Field errors name body properties, so a query, path or header parameter that fails gets a
    # problem of its own. No operation takes one that can fail today.
    if not all(_location(entry)[:1] == ("body",) for entry in errors):
        locations = ", ".join(".".join(_location(entry)) for entry in errors)
        return _about_blank(
            request.url.path,
            HTTPStatus.BAD_REQUEST,
            f"The request has invalid parameters: {locations}.",
        )

    # A nested property is named by its path, as "tags.0". Each property of a flat model fails
    # in one way at a time, so there is one error per field.
    field_errors = [
        FieldError(field=".".join(_location(entry)[1:]), message=_message(entry))
        for entry in errors
    ]
    fields = ", ".join(error.field for error in field_errors)
    invalid = "an invalid field" if len(field_errors) == 1 else "invalid fields"
    return _problem_response(
        ProblemDetails(
            type="/problems/validation-error",
            title="Invalid request body",
            status=HTTPStatus.BAD_REQUEST,
            detail=f"The request body has {invalid}: {fields}.",
            instance=_instance(request.url.path),
            errors=field_errors,
        )
    )


def _is_malformed(entry: Mapping[str, Any]) -> bool:
    # An error located at the body as a whole means there was no object to validate fields of:
    # the body was empty, not an object, or not sent as JSON.
    return entry["type"] == "json_invalid" or tuple(entry["loc"]) == ("body",)


def _location(entry: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(part) for part in entry["loc"])


def _message(entry: Mapping[str, Any]) -> str:
    if entry["type"] == "string_too_long":
        return f"This field must be at most {entry['ctx']['max_length']} characters."
    return _MESSAGES.get(entry["type"], entry["msg"])


def _malformed_body(request: Request) -> JSONResponse:
    return _problem_response(
        ProblemDetails(
            type="/problems/malformed-body",
            title="Malformed request body",
            status=HTTPStatus.BAD_REQUEST,
            detail="The request body must be a JSON object sent as application/json.",
            instance=_instance(request.url.path),
            errors=[],
        )
    )


async def _http_error(request: Request, error: HTTPException) -> JSONResponse:
    path = request.url.path
    match error.status_code:
        case HTTPStatus.BAD_REQUEST if error.detail == _BODY_PARSE_FAILED:
            return _malformed_body(request)
        case HTTPStatus.NOT_FOUND:
            return _about_blank(path, HTTPStatus.NOT_FOUND, f"No resource exists at {path}.")
        case HTTPStatus.METHOD_NOT_ALLOWED:
            allowed = ", ".join(_allowed_methods(request))
            return _about_blank(
                path,
                HTTPStatus.METHOD_NOT_ALLOWED,
                f"{path} does not support {request.method}. It supports {allowed}.",
                headers={"Allow": allowed},
            )
        case _:
            status = HTTPStatus(error.status_code)
            return _about_blank(path, status, str(error.detail), headers=error.headers)


def _allowed_methods(request: Request) -> list[str]:
    # Starlette's 405 lists only the methods of the first route that matched the path. Asking
    # every route whether it would take each method finds them all, however FastAPI nests the
    # routers it includes.
    routes = request.app.router.routes
    return [
        method.value
        for method in HTTPMethod
        if any(
            route.matches({**request.scope, "method": method.value})[0] is Match.FULL
            for route in routes
        )
    ]


async def _dataset_not_found(request: Request, error: DatasetNotFoundError) -> JSONResponse:
    return _problem_response(
        ProblemDetails(
            type="/problems/dataset-not-found",
            title="Dataset not found",
            status=HTTPStatus.NOT_FOUND,
            detail=f'No dataset has id "{error.dataset_id}". It may have been deleted already.',
            instance=_instance(request.url.path),
            errors=[],
        )
    )


def _about_blank(
    path: str, status: HTTPStatus, detail: str, *, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    return _problem_response(
        ProblemDetails(
            type="about:blank",
            title=status.phrase,
            status=status,
            detail=detail,
            instance=_instance(path),
            errors=[],
        ),
        headers=headers,
    )


def _instance(path: str) -> str:
    """The path as RFC 9457 requires `instance`, a URI reference.

    ASGI hands over the path percent-decoded, so an id with a space in it would otherwise put a raw
    space in the reference. Prose fields keep the decoded path, which reads better.
    """
    return quote(path)


def _problem_response(
    problem: ProblemDetails, *, headers: Mapping[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        problem.model_dump(mode="json"),
        status_code=problem.status,
        headers=headers,
        media_type=PROBLEM_MEDIA_TYPE,
    )
