import argparse
import importlib.metadata
import json
import logging
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from pydantic.alias_generators import to_camel

from catalogue.api.deps import LifespanState
from catalogue.api.routes import health
from catalogue.core.config import Settings
from catalogue.core.logging import configure_logging
from catalogue.curation.factory import select_provider_name

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        # Under uvicorn a ValidationError arrives as a long traceback through its factory loader,
        # with the one line that matters at the bottom.
        try:
            settings = Settings()
        except ValidationError as error:
            message = f"Invalid configuration in the environment or backend/.env\n{error}"
            raise SystemExit(message) from None
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[LifespanState]:
        provider_name = select_provider_name(settings)
        if provider_name == "anthropic":
            logger.info(
                "Curation provider: anthropic, model %s, host %s",
                settings.anthropic_model,
                settings.anthropic_base_url,
            )
        else:
            logger.info("Curation provider: keyword")
        yield {"curation_provider_name": provider_name}

    app = FastAPI(
        title="Data Catalogue API",
        version=importlib.metadata.version("catalogue"),
        lifespan=lifespan,
        generate_unique_id_function=lambda route: to_camel(route.name),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
        expose_headers=["Location"],
    )
    app.include_router(health.router)
    return app


def export_openapi(argv: Sequence[str] | None = None) -> None:
    """Write the OpenAPI document that the frontend types are generated from.

    The document must not depend on local configuration, so `.env` is skipped and the keyword
    provider is pinned. The file is replaced atomically so a reader never sees half of it.
    """
    parser = argparse.ArgumentParser(
        prog="catalogue-openapi", description="Write the API's OpenAPI document as JSON."
    )
    parser.add_argument("--output", type=Path, required=True, metavar="PATH", help="file to write")
    output: Path = parser.parse_args(argv).output

    app = create_app(Settings(_env_file=None, curation_provider="keyword"))
    document = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"

    temporary = output.with_name(f".{output.name}.tmp")
    temporary.write_text(document, encoding="utf-8")
    temporary.replace(output)
