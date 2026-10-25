from typing import Literal

import pytest
from pydantic import SecretStr

from catalogue.core.config import Settings
from catalogue.curation.factory import select_provider_name
from catalogue.domain.models import CurationProviderName


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
