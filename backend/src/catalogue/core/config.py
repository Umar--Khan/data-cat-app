from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from catalogue.core.logging import LogLevel

# A browser's Origin header never carries a path or trailing slash, so an entry with one would
# match nothing and every call would fail CORS without a hint why.
type Origin = Annotated[str, Field(pattern=r"^https?://[^/\s]+$")]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CATALOGUE_",
        # Anchored to backend/ rather than the working directory, so every way of starting the
        # app reads the same file.
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_ignore_empty=True,
        # A misspelt key in .env must fail startup: silently dropping it can leave `auto` in
        # charge of a checkout that holds a key, which means billed Claude calls.
        extra="forbid",
    )

    curation_provider: Literal["auto", "anthropic", "keyword"] = "auto"
    # The Anthropic variables keep their conventional names, so a key exported in the shell
    # counts. They still reach the SDK only through these fields, never by the SDK's own lookup.
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str = Field(
        default="https://api.anthropic.com",
        validation_alias="ANTHROPIC_BASE_URL",
        pattern=r"^https?://\S+$",
    )
    # A key that is not scoped to a workspace is rejected without one. The SDK applies the
    # variable only to workload-federation credentials, never to an API key.
    anthropic_workspace_id: str | None = Field(
        default=None, validation_alias="ANTHROPIC_WORKSPACE_ID"
    )
    anthropic_model: str = "claude-opus-5-5"
    anthropic_timeout_seconds: float = Field(default=20, gt=0)
    # Every call is billed. At 2 to 4 s a curation, four in flight still clear a burst of about
    # twenty creates inside the 20 s budget, far more than a team registering datasets by hand.
    anthropic_max_concurrency: int = Field(default=4, ge=1, le=64)
    # The burst equals the rate, so one address can register this many at once and then one
    # every 60 / rate seconds: enough for a person, and a cap on what one client spends on Claude.
    create_rate_limit_per_minute: int = Field(default=10, ge=1)
    keyword_delay_ms: int = Field(default=0, ge=0, le=10_000)
    cors_origins: list[Origin] = ["http://localhost:5173"]
    log_level: LogLevel = "INFO"

    @field_validator("anthropic_api_key", "anthropic_workspace_id", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: object) -> object:
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def _explicit_anthropic_requires_key(self) -> Self:
        if self.curation_provider == "anthropic" and self.anthropic_api_key is None:
            raise ValueError("CATALOGUE_CURATION_PROVIDER=anthropic requires ANTHROPIC_API_KEY")
        return self


def describe_invalid_settings(error: ValidationError) -> str:
    """The Settings errors as `location: message` lines, without the values that failed.

    `str(error)` quotes every rejected value, so a misspelt `ANTHROPIC_APIKEY=sk-ant-…` in
    `backend/.env` would print the key it holds.
    """
    lines = []
    for entry in error.errors(include_input=False, include_url=False):
        location = ".".join(str(part) for part in entry["loc"])
        lines.append(f"{location}: {entry['msg']}" if location else entry["msg"])
    return "\n".join(lines)
