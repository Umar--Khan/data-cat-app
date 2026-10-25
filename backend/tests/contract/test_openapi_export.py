import importlib.metadata
import json
from pathlib import Path

import pytest

from catalogue.app import export_openapi
from catalogue.core.config import Settings


def test_export_writes_sorted_json_with_a_trailing_newline(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"

    export_openapi(["--output", str(output)])

    text = output.read_text()
    document = json.loads(text)
    assert text == json.dumps(document, indent=2, sort_keys=True) + "\n"


def test_export_describes_the_api(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"

    export_openapi(["--output", str(output)])

    document = json.loads(output.read_text())
    assert document["info"] == {
        "title": "Data Catalogue API",
        "version": importlib.metadata.version("catalogue"),
    }
    assert document["paths"]["/health"]["get"]["operationId"] == "getHealth"
    assert {"Health", "CurationProviderName"} <= document["components"]["schemas"].keys()


def test_export_replaces_an_existing_file_and_leaves_no_temporary_file(tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"
    output.write_text("stale")

    export_openapi(["--output", str(output)])

    assert json.loads(output.read_text())["info"]["title"] == "Data Catalogue API"
    assert [path.name for path in tmp_path.iterdir()] == ["openapi.json"]


def test_export_ignores_local_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("CATALOGUE_LOG_LEVEL=not-a-level\n")
    monkeypatch.setitem(Settings.model_config, "env_file", env_file)
    monkeypatch.setenv("CATALOGUE_CURATION_PROVIDER", "anthropic")
    output = tmp_path / "openapi.json"

    export_openapi(["--output", str(output)])

    assert output.exists()


def test_export_requires_an_output_path() -> None:
    with pytest.raises(SystemExit) as excinfo:
        export_openapi([])

    assert excinfo.value.code == 2
