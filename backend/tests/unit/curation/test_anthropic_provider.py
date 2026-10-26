"""Claude provider tests: the real `AsyncAnthropic` over `httpx2.MockTransport`, with no network.

Why the SDK runs for real, and which of its behaviours these cases pin, is in specs/curation.md
under "Claude provider tests".
"""

import json
import logging
import time
from collections import deque
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

import httpx2
import pytest
from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    CredentialsError,
    DefaultAsyncHttpxClient,
    InternalServerError,
    NotFoundError,
    OverloadedError,
    PermissionDeniedError,
    RateLimitError,
)
from pydantic import SecretStr, ValidationError

from catalogue.core.config import Settings
from catalogue.curation.anthropic_provider import AnthropicCurationProvider
from catalogue.curation.base import CurationDraft, CurationError, CurationFailure
from catalogue.curation.factory import build_client
from catalogue.curation.prompt import SYSTEM_PROMPT, render_dataset
from catalogue.domain.models import NewDataset

LOGGER = "catalogue.curation.anthropic_provider"
TRADE_CONFIRMATIONS = NewDataset(
    name="Trade Confirmations",
    owner="Middle Office",
    description=(
        "Daily export of confirmed trades including instrument type, counterparty, notional "
        "value, and settlement date."
    ),
)
DRAFT = CurationDraft(
    tags=("trading", "finance", "settlements", "daily"),
    summary="A daily export of confirmed trades covering instrument type and counterparty.",
)
DRAFT_JSON = json.dumps({"tags": list(DRAFT.tags), "summary": DRAFT.summary})
THINKING = {"type": "thinking", "thinking": "", "signature": "sig"}
RETRY_SOON = {"retry-after-ms": "1"}

type Reply = httpx2.Response | Exception


class FakeAnthropicApi:
    """Answers each request with the next canned reply, and keeps every request it receives."""

    def __init__(self, *replies: Reply) -> None:
        self._replies = deque(replies)
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        reply = self._replies.popleft()
        if isinstance(reply, Exception):
            raise reply
        return reply

    @property
    def body(self) -> object:
        return json.loads(self.requests[-1].content)


def make_settings(
    *, model: str = "claude-opus-5-5", timeout: float = 20, workspace: str | None = None
) -> Settings:
    return Settings(
        _env_file=None,
        curation_provider="anthropic",
        ANTHROPIC_API_KEY=SecretStr("sk-ant-test"),
        ANTHROPIC_BASE_URL="https://claude.test",
        ANTHROPIC_WORKSPACE_ID=workspace,
        anthropic_model=model,
        anthropic_timeout_seconds=timeout,
    )


def text(value: str) -> Mapping[str, object]:
    return {"type": "text", "text": value}


def message(
    *content: Mapping[str, object],
    stop_reason: str = "end_turn",
    model: str = "claude-opus-5-5",
    usage: Mapping[str, object] | None = None,
    stop_details: Mapping[str, object] | None = None,
) -> httpx2.Response:
    return httpx2.Response(
        200,
        headers={"request-id": "req_test"},
        json={
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": model,
            "content": list(content),
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "stop_details": stop_details,
            "usage": usage or {"input_tokens": 300, "output_tokens": 90},
        },
    )


def completed() -> httpx2.Response:
    return message(THINKING, text(DRAFT_JSON))


def api_error(
    status: int, error_type: str, *, headers: dict[str, str] | None = None
) -> httpx2.Response:
    return httpx2.Response(
        status,
        headers={"request-id": "req_error", **(headers or {})},
        json={
            "type": "error",
            "error": {"type": error_type, "message": f"Canned {error_type}"},
            "request_id": "req_error",
        },
    )


@asynccontextmanager
async def open_provider(
    api: FakeAnthropicApi, settings: Settings
) -> AsyncIterator[AnthropicCurationProvider]:
    http_client = DefaultAsyncHttpxClient(transport=httpx2.MockTransport(api))
    async with build_client(settings, http_client=http_client) as client:
        yield AnthropicCurationProvider(
            client,
            model=settings.anthropic_model,
            timeout_seconds=settings.anthropic_timeout_seconds,
        )


async def curate(api: FakeAnthropicApi, settings: Settings | None = None) -> CurationDraft:
    async with open_provider(api, settings or make_settings()) as provider:
        return await provider.curate(TRADE_CONFIRMATIONS)


async def curation_failure(
    api: FakeAnthropicApi, settings: Settings | None = None
) -> CurationError:
    with pytest.raises(CurationError) as raised:
        await curate(api, settings)
    return raised.value


@pytest.mark.anyio
async def test_names_itself_and_the_configured_model() -> None:
    async with open_provider(
        FakeAnthropicApi(), make_settings(model="claude-sonnet-5-5")
    ) as provider:
        assert provider.name == "anthropic"
        assert provider.model == "claude-sonnet-5-5"


@pytest.mark.anyio
async def test_returns_the_draft_as_claude_wrote_it() -> None:
    api = FakeAnthropicApi(completed())

    assert await curate(api) == DRAFT
    assert len(api.requests) == 1


@pytest.mark.anyio
async def test_returns_more_than_was_asked_for_so_the_normaliser_can_trim_it() -> None:
    tags = [f"tag-{number}" for number in range(9)]
    summary = "A long one. " * 40
    api = FakeAnthropicApi(message(text(json.dumps({"tags": tags, "summary": summary}))))

    assert await curate(api) == CurationDraft(tags=tuple(tags), summary=summary)


@pytest.mark.anyio
async def test_sends_the_request_the_spec_describes() -> None:
    api = FakeAnthropicApi(completed())

    await curate(api)

    body = api.body
    assert isinstance(body, dict)
    # The descriptions are prose written for Claude, so only their presence is checked here.
    schema = body["output_config"]["format"]["schema"]
    descriptions = [
        schema.pop("description"),
        schema["properties"]["tags"].pop("description"),
        schema["properties"]["summary"].pop("description"),
    ]
    assert all(isinstance(description, str) and description for description in descriptions)
    assert body == {
        "model": "claude-opus-5-5",
        "max_tokens": 4096,
        "system": [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": render_dataset(TRADE_CONFIRMATIONS)}],
        "output_config": {
            "effort": "low",
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "title": "CurationDraft",
                    "properties": {
                        "tags": {
                            "type": "array",
                            "title": "Tags",
                            "items": {"type": "string"},
                        },
                        "summary": {"type": "string", "title": "Summary"},
                    },
                    "required": ["tags", "summary"],
                    "additionalProperties": False,
                },
            },
        },
        "fallbacks": "default",
    }
    assert api.requests[0].headers["anthropic-beta"] == "server-side-fallback-2026-07-01"


@pytest.mark.anyio
async def test_sends_the_settings_key_and_host_whatever_the_sdk_would_discover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-environment")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token-from-environment")
    api = FakeAnthropicApi(completed())

    await curate(api)

    request = api.requests[0]
    assert request.url == "https://claude.test/v1/messages"
    assert request.headers["authorization"] == "Bearer sk-ant-test"


@pytest.mark.anyio
async def test_sends_the_settings_workspace_for_a_key_not_scoped_to_one() -> None:
    api = FakeAnthropicApi(completed())

    await curate(api, make_settings(workspace="wrkspc_test"))

    assert api.requests[0].headers["anthropic-workspace-id"] == "wrkspc_test"


@pytest.mark.anyio
async def test_sends_no_workspace_when_none_is_set() -> None:
    api = FakeAnthropicApi(completed())

    await curate(api)

    assert "anthropic-workspace-id" not in api.requests[0].headers


@pytest.mark.anyio
@pytest.mark.parametrize(
    "model", ["claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"]
)
async def test_asks_for_the_refusal_fallback_on_models_that_accept_it(model: str) -> None:
    api = FakeAnthropicApi(completed())

    await curate(api, make_settings(model=model))

    assert api.requests[0].headers["anthropic-beta"] == "server-side-fallback-2026-07-01"
    assert isinstance(api.body, dict)
    assert api.body["fallbacks"] == "default"


@pytest.mark.anyio
@pytest.mark.parametrize("model", ["claude-haiku-5-5", "claude-opus-4-8"])
async def test_leaves_the_refusal_fallback_out_for_other_models(model: str) -> None:
    api = FakeAnthropicApi(completed())

    await curate(api, make_settings(model=model))

    assert "anthropic-beta" not in api.requests[0].headers
    assert isinstance(api.body, dict)
    assert "fallbacks" not in api.body
    assert api.body["model"] == model


@pytest.mark.anyio
async def test_logs_the_serving_model_usage_and_request_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    usage: dict[str, object] = {
        "input_tokens": 310,
        "output_tokens": 95,
        "cache_read_input_tokens": 1200,
        "cache_creation_input_tokens": 0,
    }
    api = FakeAnthropicApi(message(THINKING, text(DRAFT_JSON), usage=usage))

    await curate(api)

    assert [(record.levelno, record.getMessage()) for record in caplog.records] == [
        (
            logging.INFO,
            "Claude curation served by claude-opus-5-5: fallback=False input_tokens=310 "
            "cache_read_input_tokens=1200 cache_creation_input_tokens=0 output_tokens=95 "
            "request_id=req_test",
        )
    ]


@pytest.mark.anyio
async def test_logs_when_a_fallback_model_served(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    declined = {
        "type": "message",
        "model": "claude-opus-5-5",
        "input_tokens": 300,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    served = {**declined, "type": "fallback_message", "model": "claude-opus-5", "output_tokens": 80}
    switch = {
        "type": "fallback",
        "from": {"model": "claude-opus-5-5"},
        "to": {"model": "claude-opus-5"},
        "trigger": {"category": "cyber"},
    }
    usage: dict[str, object] = {
        "input_tokens": 300,
        "output_tokens": 80,
        "iterations": [declined, served],
    }
    api = FakeAnthropicApi(message(switch, text(DRAFT_JSON), model="claude-opus-5", usage=usage))

    assert await curate(api) == DRAFT
    assert caplog.messages == [
        "Claude curation served by claude-opus-5: fallback=True input_tokens=300 "
        "cache_read_input_tokens=0 cache_creation_input_tokens=0 output_tokens=80 "
        "request_id=req_test"
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "error_type", "sdk_error"),
    [
        pytest.param(400, "invalid_request_error", BadRequestError, id="400"),
        pytest.param(401, "authentication_error", AuthenticationError, id="401"),
        pytest.param(402, "billing_error", APIStatusError, id="402"),
        pytest.param(403, "permission_error", PermissionDeniedError, id="403"),
        pytest.param(404, "not_found_error", NotFoundError, id="404-bad-model"),
    ],
)
async def test_a_rejected_request_is_misconfigured_and_not_retried(
    status: int, error_type: str, sdk_error: type[APIStatusError]
) -> None:
    api = FakeAnthropicApi(api_error(status, error_type))

    failure = await curation_failure(api, make_settings(model="claude-nope"))

    assert failure.failure is CurationFailure.MISCONFIGURED
    assert type(failure.__cause__) is sdk_error
    assert len(api.requests) == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "error_type", "sdk_error", "expected"),
    [
        pytest.param(408, "timeout_error", APIStatusError, CurationFailure.TIMEOUT, id="408"),
        pytest.param(
            429, "rate_limit_error", RateLimitError, CurationFailure.RATE_LIMITED, id="429"
        ),
        pytest.param(500, "api_error", InternalServerError, CurationFailure.UNAVAILABLE, id="500"),
        pytest.param(
            529, "overloaded_error", OverloadedError, CurationFailure.UNAVAILABLE, id="529"
        ),
    ],
)
async def test_a_retryable_status_fails_after_the_one_retry(
    status: int, error_type: str, sdk_error: type[APIStatusError], expected: CurationFailure
) -> None:
    api = FakeAnthropicApi(
        api_error(status, error_type, headers=RETRY_SOON),
        api_error(status, error_type, headers=RETRY_SOON),
    )

    failure = await curation_failure(api)

    assert failure.failure is expected
    assert type(failure.__cause__) is sdk_error
    assert len(api.requests) == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "error_type"),
    [(429, "rate_limit_error"), (500, "api_error"), (529, "overloaded_error")],
)
async def test_the_one_retry_can_still_succeed(status: int, error_type: str) -> None:
    api = FakeAnthropicApi(api_error(status, error_type, headers=RETRY_SOON), completed())

    assert await curate(api) == DRAFT
    assert len(api.requests) == 2


@pytest.mark.anyio
async def test_an_unreachable_api_is_unavailable() -> None:
    api = FakeAnthropicApi(httpx2.ConnectError("refused"), httpx2.ConnectError("refused"))

    failure = await curation_failure(api)

    assert failure.failure is CurationFailure.UNAVAILABLE
    assert type(failure.__cause__) is APIConnectionError
    assert len(api.requests) == 2


@pytest.mark.anyio
async def test_an_sdk_timeout_is_a_timeout_not_a_connection_failure() -> None:
    api = FakeAnthropicApi(httpx2.ReadTimeout("slow"), httpx2.ReadTimeout("slow"))

    failure = await curation_failure(api)

    assert failure.failure is CurationFailure.TIMEOUT
    assert type(failure.__cause__) is APITimeoutError


@pytest.mark.anyio
async def test_the_budget_cuts_off_an_uncapped_retry_after() -> None:
    api = FakeAnthropicApi(api_error(429, "rate_limit_error", headers={"retry-after": "3600"}))
    started = time.monotonic()

    failure = await curation_failure(api, make_settings(timeout=0.05))

    assert failure.failure is CurationFailure.TIMEOUT
    assert type(failure.__cause__) is TimeoutError
    assert time.monotonic() - started < 1
    assert len(api.requests) == 1


@pytest.mark.anyio
async def test_leaves_errors_outside_the_failures_table_to_the_service() -> None:
    api = FakeAnthropicApi(CredentialsError("No credentials could be loaded."))

    with pytest.raises(CredentialsError):
        await curate(api)


@pytest.mark.anyio
async def test_a_refusal_is_refused_and_logged_with_its_category(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    api = FakeAnthropicApi(
        message(
            stop_reason="refusal",
            stop_details={"type": "refusal", "category": "cyber", "explanation": None},
        )
    )

    failure = await curation_failure(api)

    assert failure.failure is CurationFailure.REFUSED
    assert [(record.levelno, record.getMessage()) for record in caplog.records] == [
        (
            logging.WARNING,
            "Claude curation response unusable: stop_reason=refusal refusal_category=cyber "
            "model=claude-opus-5-5 fallback=False request_id=req_test",
        )
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("reply", "cause"),
    [
        pytest.param(
            message(THINKING, text(DRAFT_JSON), stop_reason="max_tokens"),
            None,
            id="max-tokens",
        ),
        pytest.param(
            message(THINKING, text('{"tags": ["trading", "fin'), stop_reason="max_tokens"),
            ValidationError,
            id="truncated-json",
        ),
        pytest.param(
            message(
                THINKING,
                text('{"tags": ["trading", "fin'),
                stop_reason="refusal",
                stop_details={"type": "refusal", "category": "cyber", "explanation": None},
            ),
            ValidationError,
            id="refusal-partway",
        ),
        pytest.param(
            message(text("I would tag this trading and finance.")),
            ValidationError,
            id="prose",
        ),
        pytest.param(
            message(text('{"tags": ["trading"]}')),
            ValidationError,
            id="missing-summary",
        ),
        pytest.param(message(THINKING), None, id="no-parsed-output"),
    ],
)
async def test_an_unusable_response_is_invalid_output(
    reply: httpx2.Response, cause: type[Exception] | None
) -> None:
    failure = await curation_failure(FakeAnthropicApi(reply))

    assert failure.failure is CurationFailure.INVALID_OUTPUT
    assert (None if failure.__cause__ is None else type(failure.__cause__)) is cause


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("stop_reason", "stop_details"),
    [
        pytest.param("max_tokens", None, id="cut-off"),
        pytest.param(
            "refusal",
            {"type": "refusal", "category": "cyber", "explanation": None},
            id="refusal-partway",
        ),
    ],
)
async def test_an_unparseable_response_is_logged_with_its_stop_reason_and_request_id(
    caplog: pytest.LogCaptureFixture, stop_reason: str, stop_details: Mapping[str, object] | None
) -> None:
    caplog.set_level(logging.INFO, logger=LOGGER)
    api = FakeAnthropicApi(
        message(
            THINKING,
            text('{"tags": ["trading", "fin'),
            stop_reason=stop_reason,
            stop_details=stop_details,
        )
    )

    await curation_failure(api)

    assert [(record.levelno, record.getMessage()) for record in caplog.records] == [
        (
            logging.WARNING,
            f"Claude curation response unparseable: stop_reason={stop_reason} request_id=req_test",
        )
    ]
