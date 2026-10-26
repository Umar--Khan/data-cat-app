import time
from typing import Literal

import pytest
from anthropic import AsyncAnthropic, Timeout
from pydantic import SecretStr

from catalogue.core.config import Settings
from catalogue.curation import factory
from catalogue.curation.anthropic_provider import AnthropicCurationProvider
from catalogue.curation.factory import build_client, select_provider_name
from catalogue.curation.keyword_provider import KeywordCurationProvider
from catalogue.domain.models import CurationProviderName, NewDataset


@pytest.mark.parametrize(
    ("configured", "key", "expected"),
    [
        pytest.param("keyword", None, "keyword", id="keyword-without-key"),
        pytest.param("keyword", "sk-ant-test", "keyword", id="keyword-wins-over-a-key"),
        pytest.param("auto", None, "keyword", id="auto-without-key"),
        pytest.param("auto", "   ", "keyword", id="auto-with-blank-key"),
        pytest.param("auto", "sk-ant-test", "anthropic", id="auto-with-key"),
        pytest.param("anthropic", "sk-ant-test", "anthropic", id="anthropic-with-key"),
    ],
)
def test_select_provider_name(
    configured: Literal["auto", "anthropic", "keyword"],
    key: str | None,
    expected: CurationProviderName,
) -> None:
    settings = Settings(
        _env_file=None,
        curation_provider=configured,
        ANTHROPIC_API_KEY=None if key is None else SecretStr(key),
    )

    assert select_provider_name(settings) == expected


@pytest.mark.anyio
async def test_open_curation_provider_builds_the_keyword_provider_with_its_delay() -> None:
    settings = Settings(_env_file=None, curation_provider="keyword", keyword_delay_ms=100)
    new = NewDataset(name="Payroll", owner="HR Team", description="Monthly payroll runs.")

    async with factory.open_curation_provider(settings) as provider:
        started = time.perf_counter()
        await provider.curate(new)
        elapsed = time.perf_counter() - started

    assert isinstance(provider, KeywordCurationProvider)
    assert elapsed >= 0.09


@pytest.mark.anyio
async def test_client_takes_its_key_host_deadline_and_one_retry_from_settings() -> None:
    settings = Settings(
        _env_file=None,
        ANTHROPIC_API_KEY=SecretStr("sk-ant-test"),
        ANTHROPIC_BASE_URL="https://claude.test",
        anthropic_timeout_seconds=12.5,
    )

    async with build_client(settings) as client:
        assert client.api_key == "sk-ant-test"
        assert str(client.base_url) == "https://claude.test"
        assert client.timeout == Timeout(12.5, connect=5)
        assert client.max_retries == 1


def test_client_refuses_to_start_without_a_key() -> None:
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        build_client(Settings(_env_file=None, curation_provider="keyword"))


@pytest.fixture
def built_clients(monkeypatch: pytest.MonkeyPatch) -> list[AsyncAnthropic]:
    """Every SDK client the factory builds, so a test can see whether it was closed."""
    clients: list[AsyncAnthropic] = []

    def build_and_record(settings: Settings) -> AsyncAnthropic:
        clients.append(build_client(settings))
        return clients[-1]

    monkeypatch.setattr(factory, "build_client", build_and_record)
    return clients


@pytest.mark.anyio
async def test_open_curation_provider_builds_claude_from_settings_and_closes_its_client(
    built_clients: list[AsyncAnthropic],
) -> None:
    settings = Settings(
        _env_file=None, ANTHROPIC_API_KEY=SecretStr("sk-ant-test"), anthropic_model="claude-test"
    )

    async with factory.open_curation_provider(settings) as provider:
        [client] = built_clients
        assert not client.is_closed()

    assert isinstance(provider, AnthropicCurationProvider)
    assert provider.model == "claude-test"
    assert client.is_closed()


@pytest.mark.anyio
async def test_open_curation_provider_closes_the_client_when_the_app_fails(
    built_clients: list[AsyncAnthropic],
) -> None:
    settings = Settings(_env_file=None, ANTHROPIC_API_KEY=SecretStr("sk-ant-test"))

    with pytest.raises(RuntimeError, match="startup failed"):
        async with factory.open_curation_provider(settings):
            raise RuntimeError("startup failed")

    [client] = built_clients
    assert client.is_closed()
