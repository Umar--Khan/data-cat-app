"""The brief's API checklist, run against a freshly started server.

The checks are those in specs/quality-gates.md (Live API verification). Each one restates the
brief or specs/api-contract.md, so a failure means the API is wrong: fix the code, never these
expectations.
"""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

import httpx2
from pydantic import ValidationError

from catalogue.core.config import Settings, describe_invalid_settings

TEST_PAYLOAD = {
    "name": "Trade Confirmations",
    "owner": "Middle Office",
    "description": (
        "Daily export of confirmed trades including instrument type, counterparty, "
        "notional value, and settlement date."
    ),
}
SEEDS = [("1", "Customer Transactions"), ("2", "Product Inventory"), ("3", "Employee Directory")]

KEYWORD_ENV = {
    "CATALOGUE_CURATION_PROVIDER": "keyword",
    # The dev delay exists to show the pending state in a browser; here it only slows the run.
    "CATALOGUE_KEYWORD_DELAY_MS": "0",
}
CLAUDE_ENV = {"CATALOGUE_CURATION_PROVIDER": "anthropic"}
# The offline failure configuration from specs/curation.md: real settings, no test-only code.
OFFLINE_ENV = {
    "CATALOGUE_CURATION_PROVIDER": "anthropic",
    "ANTHROPIC_API_KEY": "offline",
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:9",
}

STARTUP_SECONDS = 30
# Well past the default 20 s curation budget, so a slow Claude call fails as a curation
# timeout inside the API rather than as a client timeout here.
REQUEST_SECONDS = 60


class CheckFailedError(Exception):
    """An expectation did not hold. The message is the reason printed after FAIL."""


def expect(condition: bool, reason: str) -> None:
    if not condition:
        raise CheckFailedError(reason)


def expect_status(response: httpx2.Response, status: int) -> None:
    expect(
        response.status_code == status,
        f"got {response.status_code}, expected {status}: {response.text[:300]}",
    )


def expect_problem(response: httpx2.Response, status: int, problem_type: str) -> Any:
    expect_status(response, status)
    content_type = response.headers.get("content-type", "")
    expect(
        content_type.startswith("application/problem+json"),
        f"Content-Type is {content_type!r}, not application/problem+json",
    )
    problem = response.json()
    expect(
        problem["status"] == status and problem["type"] == problem_type,
        f"problem is {problem['status']} {problem['type']!r}, expected {status} {problem_type!r}",
    )
    return problem


def check_seeds(client: httpx2.Client) -> None:
    response = client.get("/datasets")
    expect_status(response, 200)
    listed = [(record["id"], record["name"]) for record in response.json()]
    expect(listed == SEEDS, f"listed {listed}")


def check_create(
    client: httpx2.Client, *, degraded: bool, curation_report: list[str] | None
) -> None:
    started = time.perf_counter()
    response = client.post("/datasets", json=TEST_PAYLOAD)
    latency = time.perf_counter() - started
    expect_status(response, 201)
    record = response.json()
    curation = record["curation"]
    if curation_report is not None:
        curation_report.extend(
            [
                f"tags: {', '.join(record['tags']) or '(none)'}",
                f"summary: {record['summary'] or '(none)'}",
                f"latency: {latency:.2f} s",
            ]
        )
    location = response.headers.get("location")
    expect(location == f"/datasets/{record['id']}", f"Location is {location!r}")
    if degraded:
        expect(curation["status"] == "failed", f"curation is {curation['status']!r}")
        expect(record["tags"] == [], f"tags are {record['tags']}, expected []")
        expect(record["summary"] is None, f"summary is {record['summary']!r}, expected null")
        expect(bool(curation["detail"]), "the failed curation has no detail")
    else:
        expect(
            curation["status"] == "completed",
            f"curation {curation['status']}: {curation['detail']}",
        )
        expect(bool(record["tags"]), "no tags")
        expect(bool(record["summary"]), "no summary")


def check_delete(client: httpx2.Client) -> None:
    expect_status(client.delete("/datasets/1"), 200)
    response = client.get("/datasets")
    expect_status(response, 200)
    expect(
        all(record["id"] != "1" for record in response.json()),
        "GET /datasets still lists id 1",
    )


def check_delete_again(client: httpx2.Client) -> None:
    expect_problem(client.delete("/datasets/1"), 404, "/problems/dataset-not-found")


def check_missing_field(client: httpx2.Client, field: str) -> None:
    body = {key: value for key, value in TEST_PAYLOAD.items() if key != field}
    response = client.post("/datasets", json=body)
    errors = expect_problem(response, 400, "/problems/validation-error")["errors"]
    expect(
        [error["field"] for error in errors] == [field] and bool(errors[0]["message"]),
        f"expected one error for {field}, got {errors}",
    )


def failure_reason(check: Callable[[], None]) -> str | None:
    """Run one check and say why it failed, or return None when it passed."""
    try:
        check()
    except CheckFailedError as failure:
        return str(failure)
    except httpx2.HTTPError as error:
        return f"request failed: {error!r}"
    except (LookupError, TypeError, ValueError) as error:
        return f"unexpected response body: {error!r}"
    return None


def run_checklist(client: httpx2.Client, *, degraded: bool, report_curation: bool) -> int:
    """Run every check, print one line for each, and return how many failed."""
    curation_report: list[str] = []
    created = (
        "The test payload returns 201 with Location and a failed curation"
        if degraded
        else "The test payload returns 201 with Location, tags and summary"
    )
    report = curation_report if report_curation else None
    checks: list[tuple[str, Callable[[], None]]] = [
        ("The three seeds are listed", lambda: check_seeds(client)),
        (created, lambda: check_create(client, degraded=degraded, curation_report=report)),
        (
            "DELETE /datasets/1 returns 200 and the record disappears",
            lambda: check_delete(client),
        ),
        ("Repeating it returns a 404 problem", lambda: check_delete_again(client)),
        (
            "A missing name returns a 400 problem with a name field error",
            lambda: check_missing_field(client, "name"),
        ),
        (
            "A missing description returns a 400 problem with a description field error",
            lambda: check_missing_field(client, "description"),
        ),
    ]
    failed = 0
    for number, (title, check) in enumerate(checks, start=1):
        reason = failure_reason(check)
        if reason is None:
            print(f"PASS  {number}. {title}", flush=True)
        else:
            failed += 1
            print(f"FAIL  {number}. {title}: {reason}", flush=True)
        for line in curation_report:
            print(f"        {line}", flush=True)
        curation_report.clear()
    print(f"{len(checks) - failed} of {len(checks)} checks passed.", flush=True)
    return failed


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
        return port


def wait_for_health(client: httpx2.Client, server: subprocess.Popen[bytes]) -> str:
    """Return the active curation provider once the server answers `/health`."""
    deadline = time.monotonic() + STARTUP_SECONDS
    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise SystemExit(
                f"The server exited with code {server.returncode} before answering /health. "
                "Its output is above."
            )
        try:
            response = client.get("/health", timeout=1)
        except httpx2.TransportError:
            time.sleep(0.1)
            continue
        if response.status_code != httpx2.codes.OK:
            raise SystemExit(f"/health answered {response.status_code}: {response.text[:300]}")
        provider: str = response.json()["curationProvider"]
        return provider
    raise SystemExit(f"The server did not answer /health within {STARTUP_SECONDS} s.")


@contextmanager
def fresh_server(environment: Mapping[str, str]) -> Iterator[tuple[httpx2.Client, str]]:
    """Start the app as `pnpm dev` does, yield a client for it and its provider, then stop it.

    A port nothing else holds means every run starts from the seeds and never touches a running
    dev server.
    """
    port = free_port()
    # Uvicorn's lifecycle lines would bury the results. The catalogue loggers keep their own
    # level, so the provider line at startup and Claude's usage line still appear.
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "catalogue.app:create_app",
        "--factory",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    server = subprocess.Popen(command, env={**os.environ, **environment})  # noqa: S603
    try:
        # trust_env=False keeps a proxy from the environment out of loopback requests.
        with httpx2.Client(
            base_url=f"http://127.0.0.1:{port}", timeout=REQUEST_SECONDS, trust_env=False
        ) as client:
            yield client, wait_for_health(client, server)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()


def _load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as error:
        raise SystemExit(
            "Invalid configuration in the environment or backend/.env. No server was started.\n"
            f"{describe_invalid_settings(error)}"
        ) from None


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pnpm verify:api",
        description="Run the brief's API checklist against a freshly started server.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--degraded",
        action="store_true",
        help="use the offline failure configuration, so every curation fails",
    )
    mode.add_argument(
        "--provider",
        choices=["keyword", "anthropic"],
        default="keyword",
        help="curation provider (default: keyword); anthropic makes one billed Claude call",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    live = args.provider == "anthropic"
    # Fails fast instead of starting a server that would only fail Settings validation. Settings
    # reads the environment and backend/.env exactly as that server would.
    if live and _load_settings().anthropic_api_key is None:
        raise SystemExit(
            "--provider anthropic needs ANTHROPIC_API_KEY, in the environment or backend/.env. "
            "No server was started."
        )
    environment = OFFLINE_ENV if args.degraded else CLAUDE_ENV if live else KEYWORD_ENV
    expected_provider = environment["CATALOGUE_CURATION_PROVIDER"]
    # SIGTERM, from CI or forwarded by uv, would otherwise end this process at once and leave
    # the server running. As KeyboardInterrupt it runs the same cleanup as Ctrl-C.
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    try:
        with fresh_server(environment) as (client, provider):
            if provider != expected_provider:
                raise SystemExit(
                    f"/health reports curation provider {provider!r}, expected "
                    f"{expected_provider!r}."
                )
            profile = " (offline failure configuration)" if args.degraded else ""
            print(f"Verifying {client.base_url}, curation provider {provider}{profile}", flush=True)
            failed = run_checklist(client, degraded=args.degraded, report_curation=live)
    except KeyboardInterrupt:
        print("Interrupted. The server was stopped.", file=sys.stderr)
        return 130
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
