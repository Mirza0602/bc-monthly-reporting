"""Tests for the company probe."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from src.bc_client import BusinessCentralClient
from src.inventory import main, run_probe
from test_bc_client import COMPANY, SECRET, FakeResponse, FakeSession, make_client, ok


@pytest.fixture(autouse=True)
def isolate_probe_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("src.inventory.probe_directory", lambda: tmp_path / "probe")
    monkeypatch.setattr("src.inventory.company_file", lambda: tmp_path / ".env.local")


def _install_client(monkeypatch: pytest.MonkeyPatch, session: FakeSession) -> BusinessCentralClient:
    client = make_client(session)
    monkeypatch.setattr("src.inventory.BusinessCentralClient.from_env", lambda: client)
    return client


def test_probe_lists_both_routes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    companies = [{"id": COMPANY, "displayName": "CRONUS AG", "name": "CRONUS"}]
    session = FakeSession([ok(companies), ok(companies)])
    _install_client(monkeypatch, session)

    assert main(["--probe"]) == 1
    captured = capsys.readouterr()
    assert "Catalog: 9 entities on v2.0, 22 entities on microsoft/analytics/v1.0." in captured.out
    assert "v2.0: 1 company" in captured.out
    assert "microsoft/analytics/v1.0: 1 company" in captured.out
    assert "- CRONUS AG" in captured.out
    assert COMPANY not in captured.out
    assert "No company whose name contains CRONUS DE" in captured.err
    assert len(session.calls) == 2
    assert session.calls[0]["url"].endswith("/api/v2.0/companies")
    assert "/api/microsoft/analytics/v1.0/companies" in session.calls[1]["url"]
    assert all(call["headers"]["Prefer"] == "odata.maxpagesize=20000" for call in session.calls)
    assert SECRET not in captured.out
    assert SECRET not in captured.err
    assert SECRET not in repr(session.calls)


def test_probe_aborts_when_analytics_returns_http_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = FakeSession(
        [
            ok([{"id": COMPANY, "displayName": "CRONUS AG"}]),
            FakeResponse(404, text="missing"),
        ]
    )
    _install_client(monkeypatch, session)
    assert main(["--probe"]) == 1
    captured = capsys.readouterr()
    assert "CRONUS AG" in captured.out
    assert "Analytics route microsoft/analytics/v1.0 did not respond" in captured.err
    assert "HTTP 404" in captured.err


def test_probe_aborts_when_analytics_connection_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = FakeSession(
        [
            ok([{"id": COMPANY, "displayName": "CRONUS AG"}]),
            requests.ConnectionError("timed out"),
        ]
    )
    _install_client(monkeypatch, session)
    assert main(["--probe"]) == 1
    captured = capsys.readouterr()
    assert "Analytics route microsoft/analytics/v1.0 did not respond" in captured.err
    assert "Connection failed" in captured.err
    assert SECRET not in captured.err


def test_probe_aborts_when_analytics_company_list_is_empty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = FakeSession(
        [
            ok([{"id": COMPANY, "displayName": "CRONUS AG"}]),
            ok([]),
        ]
    )
    _install_client(monkeypatch, session)
    assert main(["--probe"]) == 1
    error = capsys.readouterr().err
    assert "responded with no companies" in error
    assert "Power BI Connector" in error


def test_probe_without_configuration(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("src.bc_client.load_dotenv", lambda *_args, **_kwargs: False)
    for name in (
        "BC_TENANT_ID",
        "BC_CLIENT_ID",
        "BC_CLIENT_SECRET",
        "BC_ENVIRONMENT",
        "BC_COMPANY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BC_CLIENT_SECRET", SECRET)
    monkeypatch.setenv("BC_CLIENT_ID", "client-id")
    assert main(["--probe"]) == 1
    captured = capsys.readouterr()
    assert "Catalog:" in captured.out
    assert "BC_TENANT_ID" in captured.err
    assert SECRET not in captured.out
    assert SECRET not in captured.err
    assert "Traceback" not in captured.err


def test_without_probe_returns_usage() -> None:
    assert main([]) == 2


def test_probe_gets_each_entity_once_with_top_and_count(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    catalog = tmp_path / "entities.yaml"
    catalog.write_text(
        "\n".join(
            [
                "v2.0:",
                "  - entity_set: accounts",
                "    select:",
                "      - id",
                "    filter_field: null",
                "    key: id",
                '"microsoft/analytics/v1.0":',
                "  - entity_set: customers",
                "    select:",
                "      - customerNo",
                "    filter_field: null",
                "    key: customerNo",
                "",
            ]
        ),
        encoding="utf-8",
    )
    companies = [{"id": COMPANY, "displayName": "CRONUS Deutschland", "name": "CRONUS DE"}]
    session = FakeSession(
        [
            ok(companies),
            ok(companies),
            FakeResponse(
                200,
                {"@odata.count": 4, "value": [{"id": "1", "number": "1000"}]},
                text='{"@odata.count": 4, "value": [{"id": "1", "number": "1000"}]}',
            ),
            FakeResponse(
                404,
                {"error": {"code": "BadRequest_NotFound", "message": "Resource not found"}},
                text='{"error": {"message": "Resource not found"}}',
            ),
        ]
    )
    _install_client(monkeypatch, session)
    assert run_probe(catalog) == 1
    captured = capsys.readouterr()
    entity_calls = session.calls[2:]
    assert [call["params"] for call in entity_calls] == [
        {"$top": "1", "$count": "true"},
        {"$top": "1", "$count": "true"},
    ]
    assert entity_calls[0]["url"].endswith(f"/companies({COMPANY})/accounts")
    assert entity_calls[1]["url"].endswith(f"/companies({COMPANY})/customers")
    assert sum("customers" in call["url"] for call in session.calls) == 1
    assert "accounts" in captured.out
    assert "Analytics" in captured.out
    assert "Resource not found" in captured.err
    assert "HTTP 404" in captured.err
    stored = (tmp_path / ".env.local").read_text(encoding="utf-8")
    assert stored.strip() == f"BC_COMPANY={COMPANY}"
    assert SECRET not in captured.out
    assert SECRET not in captured.err
    assert SECRET not in stored

