from typing import Any

from fastapi import FastAPI

from catalogue.api.problems import PROBLEM_MEDIA_TYPE
from catalogue.api.schemas import ProblemDetails


def problem(description: str) -> dict[str, Any]:
    """A `responses=` entry documenting an error status with a ProblemDetails body."""
    return {"model": ProblemDetails, "description": description}


class CatalogueAPI(FastAPI):
    """FastAPI with error bodies documented under the media type they are sent with.

    FastAPI documents every `responses=` model as application/json, while problems are sent as
    application/problem+json. The generated TypeScript client keys bodies by media type, and
    schemathesis checks the media type of each response, so the document has to say what is sent.
    """

    def openapi(self) -> dict[str, Any]:
        if self.openapi_schema is None:
            self.openapi_schema = _document_problems(super().openapi())
        return self.openapi_schema


def _document_problems(document: dict[str, Any]) -> dict[str, Any]:
    for path_item in document["paths"].values():
        for operation in path_item.values():
            for status, response in operation["responses"].items():
                content = response.get("content")
                if status.startswith(("4", "5")) and content is not None:
                    content[PROBLEM_MEDIA_TYPE] = content.pop("application/json")
    return document
