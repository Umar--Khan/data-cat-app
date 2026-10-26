import argparse
import importlib.metadata
import json
import logging
from collections.abc import AsyncGenerator, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from pydantic.alias_generators import to_camel

from catalogue.api.deps import LifespanState
from catalogue.api.openapi import CatalogueAPI
from catalogue.api.problems import UnhandledErrorMiddleware, exception_handlers
from catalogue.api.routes import datasets, health
from catalogue.core.config import Settings
from catalogue.core.logging import configure_logging
from catalogue.curation.base import CurationProvider
from catalogue.curation.factory import open_curation_provider
from catalogue.curation.service import CurationService
from catalogue.repositories.base import DatasetRepository
from catalogue.repositories.memory import InMemoryDatasetRepository
from catalogue.repositories.seeds import seed_datasets
from catalogue.services.datasets import Clock, DatasetService, utc_now

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    repository: DatasetRepository | None = None,
    curation_provider: CurationProvider | None = None,
    clock: Clock = utc_now,
) -> FastAPI:
    """Build the app. Whatever is not injected, the lifespan builds from settings at startup."""
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
        async with AsyncExitStack() as resources:
            provider = curation_provider
            if provider is None:
                provider = await resources.enter_async_context(open_curation_provider(settings))
            if provider.name == "anthropic":
                logger.info(
                    "Curation provider: anthropic, model %s, host %s",
                    provider.model,
                    settings.anthropic_base_url,
                )
            else:
                logger.info("Curation provider: keyword")
            # Built here rather than in create_app, so every startup, including each --reload
            # restart, begins from the seeds stamped with that startup's time.
            store = repository
            if store is None:
                store = InMemoryDatasetRepository(seed_datasets(clock()))
            yield {
                "datasets": DatasetService(store, CurationService(provider), clock),
                "curation_provider_name": provider.name,
            }

    app = CatalogueAPI(
        title="Data Catalogue API",
        version=importlib.metadata.version("catalogue"),
        lifespan=lifespan,
        generate_unique_id_function=lambda route: to_camel(route.name),
        exception_handlers=exception_handlers(),
        # Starlette would answer a trailing slash with a bare 307 to an absolute URL built from
        # the Host header. An unknown path gets a 404 problem like any other.
        redirect_slashes=False,
    )
    # Middleware added later wraps middleware added earlier, so CORS wraps the error middleware
    # and a 500 problem still carries CORS headers.
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type"],
        expose_headers=["Location"],
    )
    app.include_router(datasets.router)
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
