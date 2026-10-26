import re
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from catalogue.core.config import Settings, describe_invalid_settings

ENV_EXAMPLE = Path(__file__).parents[3] / ".env.example"


def test_defaults_match_the_configuration_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_BASE_URL")

    settings = Settings(_env_file=None)

    assert settings.curation_provider == "auto"
    assert settings.anthropic_api_key is None
    assert settings.anthropic_base_url == "https://api.anthropic.com"
    assert settings.anthropic_workspace_id is None
    assert settings.anthropic_model == "claude-opus-5-5"
    assert settings.anthropic_timeout_seconds == 20
    assert settings.anthropic_max_concurrency == 4
    assert settings.create_rate_limit_per_minute == 10
    assert settings.keyword_delay_ms == 0
    assert settings.cors_origins == ["http://localhost:5173"]
    assert settings.log_level == "INFO"


@pytest.mark.parametrize("value", ["", " ", "\t\n  "])
def test_blank_key_in_the_environment_is_unset(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", value)

    assert Settings(_env_file=None).anthropic_api_key is None


@pytest.mark.parametrize("value", ["", " ", "\t\n  "])
def test_blank_workspace_in_the_environment_is_unset(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", value)

    assert Settings(_env_file=None).anthropic_workspace_id is None


def test_blank_key_passed_directly_is_unset() -> None:
    assert Settings(_env_file=None, ANTHROPIC_API_KEY=SecretStr("   ")).anthropic_api_key is None


def test_key_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "  sk-ant-test\n")

    key = Settings(_env_file=None).anthropic_api_key

    assert key is not None
    assert key.get_secret_value() == "sk-ant-test"


def test_anthropic_variables_are_read_by_their_conventional_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:4010")
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_test")

    settings = Settings(_env_file=None)

    assert settings.anthropic_api_key == SecretStr("sk-ant-test")
    assert settings.anthropic_base_url == "http://127.0.0.1:4010"
    assert settings.anthropic_workspace_id == "wrkspc_test"


def test_anthropic_variables_ignore_the_catalogue_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CATALOGUE_ANTHROPIC_API_KEY", "sk-ant-test")

    assert Settings(_env_file=None).anthropic_api_key is None


def test_app_settings_are_read_with_the_catalogue_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CATALOGUE_CURATION_PROVIDER", "keyword")
    monkeypatch.setenv("CATALOGUE_ANTHROPIC_MODEL", "claude-test-model")
    monkeypatch.setenv("CATALOGUE_ANTHROPIC_TIMEOUT_SECONDS", "2.5")
    monkeypatch.setenv("CATALOGUE_ANTHROPIC_MAX_CONCURRENCY", "2")
    monkeypatch.setenv("CATALOGUE_CREATE_RATE_LIMIT_PER_MINUTE", "1000")
    monkeypatch.setenv("CATALOGUE_KEYWORD_DELAY_MS", "1200")
    monkeypatch.setenv("CATALOGUE_CORS_ORIGINS", '["http://localhost:5180"]')
    monkeypatch.setenv("CATALOGUE_LOG_LEVEL", "DEBUG")

    settings = Settings(_env_file=None)

    assert settings.curation_provider == "keyword"
    assert settings.anthropic_model == "claude-test-model"
    assert settings.anthropic_timeout_seconds == 2.5
    assert settings.anthropic_max_concurrency == 2
    assert settings.create_rate_limit_per_minute == 1000
    assert settings.keyword_delay_ms == 1200
    assert settings.cors_origins == ["http://localhost:5180"]
    assert settings.log_level == "DEBUG"


def test_unprefixed_app_settings_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CURATION_PROVIDER", "keyword")

    assert Settings(_env_file=None).curation_provider == "auto"


def test_empty_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CATALOGUE_ANTHROPIC_MODEL", "")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "")

    settings = Settings(_env_file=None)

    assert settings.anthropic_model == "claude-opus-5-5"
    assert settings.anthropic_base_url == "https://api.anthropic.com"


def test_explicit_anthropic_without_a_key_fails_validation() -> None:
    with pytest.raises(
        ValidationError, match="CATALOGUE_CURATION_PROVIDER=anthropic requires ANTHROPIC_API_KEY"
    ):
        Settings(_env_file=None, curation_provider="anthropic")


def test_explicit_anthropic_with_a_blank_key_fails_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CATALOGUE_CURATION_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "  ")

    with pytest.raises(ValidationError, match="requires ANTHROPIC_API_KEY"):
        Settings(_env_file=None)


def test_explicit_anthropic_with_a_key_is_valid() -> None:
    settings = Settings(
        _env_file=None, curation_provider="anthropic", ANTHROPIC_API_KEY=SecretStr("sk-ant-test")
    )

    assert settings.curation_provider == "anthropic"


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("CATALOGUE_CURATION_PROVIDER", "claude"),
        ("CATALOGUE_ANTHROPIC_TIMEOUT_SECONDS", "0"),
        ("CATALOGUE_ANTHROPIC_MAX_CONCURRENCY", "0"),
        ("CATALOGUE_ANTHROPIC_MAX_CONCURRENCY", "65"),
        ("CATALOGUE_CREATE_RATE_LIMIT_PER_MINUTE", "0"),
        ("CATALOGUE_KEYWORD_DELAY_MS", "-1"),
        ("CATALOGUE_KEYWORD_DELAY_MS", "10001"),
        ("CATALOGUE_LOG_LEVEL", "VERBOSE"),
    ],
)
def test_out_of_range_values_fail_validation(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("CATALOGUE_CORS_ORIGINS", '["http://localhost:5173/"]'),
        ("CATALOGUE_CORS_ORIGINS", '["http://localhost:5173/app"]'),
        ("CATALOGUE_CORS_ORIGINS", '["localhost:5173"]'),
        ("CATALOGUE_CORS_ORIGINS", '["http://localhost:5173", "http://local host:5180"]'),
        ("ANTHROPIC_BASE_URL", "api.anthropic.com"),
        ("ANTHROPIC_BASE_URL", "ftp://api.anthropic.com"),
        ("ANTHROPIC_BASE_URL", "https://"),
    ],
)
def test_malformed_urls_fail_validation(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str
) -> None:
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError, match="String should match pattern"):
        Settings(_env_file=None)


def test_keyword_delay_accepts_its_upper_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CATALOGUE_KEYWORD_DELAY_MS", "10000")

    assert Settings(_env_file=None).keyword_delay_ms == 10_000


def test_env_file_is_read_and_the_environment_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=sk-ant-from-file\n"
        "ANTHROPIC_WORKSPACE_ID=wrkspc_from_file\n"
        "CATALOGUE_ANTHROPIC_MODEL=claude-from-file\n"
    )
    monkeypatch.setenv("CATALOGUE_ANTHROPIC_MODEL", "claude-from-shell")

    settings = Settings(_env_file=env_file)

    assert settings.anthropic_api_key == SecretStr("sk-ant-from-file")
    assert settings.anthropic_workspace_id == "wrkspc_from_file"
    assert settings.anthropic_model == "claude-from-shell"


def test_misspelt_key_in_env_file_fails_validation(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CATALOGUE_CURATION_PROVDER=keyword\n")

    with pytest.raises(ValidationError, match="catalogue_curation_provder"):
        Settings(_env_file=env_file)


def test_invalid_settings_are_described_without_the_values_they_rejected(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_APIKEY=sk-ant-misspelt-secret\nCATALOGUE_LOG_LEVEL=sk-ant-misplaced-secret\n"
    )

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=env_file)

    description = describe_invalid_settings(excinfo.value)
    assert description.splitlines() == [
        "log_level: Input should be 'DEBUG', 'INFO', 'WARNING' or 'ERROR'",
        "anthropic_apikey: Extra inputs are not permitted",
    ]
    assert "sk-ant-" not in description


def test_an_error_about_the_settings_as_a_whole_is_described_without_a_location() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None, curation_provider="anthropic")

    assert describe_invalid_settings(excinfo.value) == (
        "Value error, CATALOGUE_CURATION_PROVIDER=anthropic requires ANTHROPIC_API_KEY"
    )


def test_env_example_is_valid_and_keeps_the_key_empty() -> None:
    settings = Settings(_env_file=ENV_EXAMPLE)

    assert settings.anthropic_api_key is None
    assert settings.keyword_delay_ms == 1200


def test_env_example_lists_every_setting() -> None:
    assigned = set(re.findall(r"^(?:# )?([A-Z][A-Z0-9_]*)=", ENV_EXAMPLE.read_text(), re.MULTILINE))
    expected = {
        field.validation_alias
        if isinstance(field.validation_alias, str)
        else f"CATALOGUE_{name.upper()}"
        for name, field in Settings.model_fields.items()
    }

    assert assigned == expected
