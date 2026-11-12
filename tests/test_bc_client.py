"""Tests for the Business Central client."""

from __future__ import annotations

import logging
import traceback
from decimal import Decimal
from typing import Any

import pytest

from src.bc_client import (
    PREFER_HEADER,
    SCOPE,
    BusinessCentralClient,
    BusinessCentralError,
    ConfigurationError,
)

SECRET = "secret-value-do-not-log"
TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
COMPANY = "11111111-2222-3333-4444-555555555555"


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        payload: Any = None,
        headers: dict[str, str] | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self.headers = headers or {}
        self.text = text

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def get(
        self,
        url: str,
        params: Any = None,
        headers: Any = None,
        timeout: Any = None,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "params": params,
                "headers": dict(headers or {}),
                "timeout": timeout,
            }
        )
        if not self._responses:
            raise AssertionError(f"unexpected request {url}")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def ok(rows: list[dict[str, Any]], next_link: str | None = None) -> FakeResponse:
    payload: dict[str, Any] = {"value": rows}
    if next_link:
        payload["@odata.nextLink"] = next_link
    return FakeResponse(200, payload)


def make_client(session: FakeSession, **kwargs: Any) -> BusinessCentralClient:
    sleep = kwargs.pop("sleep", lambda _seconds: None)
    return BusinessCentralClient(
        tenant_id=TENANT,
        client_id="client-id",
        client_secret=SECRET,
        environment="Production",
        company="",
        session=session,
        token_provider=kwargs.pop("token_provider", lambda: "access-token"),
        sleep=sleep,
        **kwargs,
    )


def test_paging_sends_select_filter_and_prefer_header() -> None:
    next_link = "https://api.example.test/next-page?$skiptoken=abc"
    session = FakeSession(
        [
            ok([{"entryNo": 1}], next_link=next_link),
            ok([{"entryNo": 2}]),
        ]
    )
    client = make_client(session)
    rows = client.get_collection(
        "microsoft/analytics/v1.0",
        "incomeStatementGeneralLedgerEntries",
        select=["entryNo", "postingDate"],
        odata_filter="postingDate ge 2024-01-01",
        company_id=COMPANY,
    )

    assert rows == [{"entryNo": 1}, {"entryNo": 2}]
    first, second = session.calls
    assert first["url"] == (
        f"https://api.businesscentral.dynamics.com/v2.0/{TENANT}/Production/"
        "api/microsoft/analytics/v1.0/"
        f"companies({COMPANY})/incomeStatementGeneralLedgerEntries"
    )
    assert first["params"] == {
        "$select": "entryNo,postingDate",
        "$filter": "postingDate ge 2024-01-01",
    }
    assert second["url"] == next_link
    assert second["params"] is None
    for call in session.calls:
        assert call["headers"]["Prefer"] == PREFER_HEADER
        assert call["headers"]["Authorization"] == "Bearer access-token"
        assert call["headers"]["Accept"] == "application/json"
        assert call["timeout"] == 60
    assert SECRET not in repr(session.calls)


def test_retries_429_using_retry_after() -> None:
    slept: list[float] = []
    session = FakeSession(
        [
            FakeResponse(429, text="slow down", headers={"Retry-After": "0"}),
            ok([{"id": "1", "displayName": "CRONUS AG"}]),
        ]
    )
    client = make_client(session, sleep=slept.append)
    rows = client.list_companies("v2.0")
    assert rows == [{"id": "1", "displayName": "CRONUS AG"}]
    assert slept == [0.0]
    assert len(session.calls) == 2


def test_retries_503_with_exponential_backoff() -> None:
    slept: list[float] = []
    session = FakeSession(
        [
            FakeResponse(503, text="unavailable"),
            FakeResponse(503, text="unavailable"),
            ok([{"id": "1"}]),
        ]
    )
    client = make_client(session, sleep=slept.append, max_attempts=4)
    assert client.list_companies("v2.0") == [{"id": "1"}]
    assert slept == [1.0, 2.0]


def test_retry_after_is_capped() -> None:
    slept: list[float] = []
    session = FakeSession(
        [
            FakeResponse(429, headers={"Retry-After": "120"}),
            ok([{"id": "1"}]),
        ]
    )
    client = make_client(session, sleep=slept.append, max_attempts=2)
    assert client.list_companies("v2.0") == [{"id": "1"}]
    assert slept == [60.0]


def test_gives_up_after_max_attempts() -> None:
    slept: list[float] = []
    session = FakeSession(
        [
            FakeResponse(429, headers={"Retry-After": "0"}),
            FakeResponse(429, headers={"Retry-After": "0"}, text="still limited"),
        ]
    )
    client = make_client(session, sleep=slept.append, max_attempts=2)
    with pytest.raises(BusinessCentralError) as excinfo:
        client.list_companies("v2.0")
    assert excinfo.value.status_code == 429
    assert slept == [0.0]
    assert len(session.calls) == 2


def test_401_is_not_retried() -> None:
    slept: list[float] = []
    session = FakeSession([FakeResponse(401, text="denied")])
    client = make_client(session, sleep=slept.append)
    with pytest.raises(BusinessCentralError) as excinfo:
        client.list_companies("v2.0")
    assert excinfo.value.status_code == 401
    assert slept == []
    assert len(session.calls) == 1


def test_repeated_next_link_stops() -> None:
    url = f"https://api.businesscentral.dynamics.com/v2.0/{TENANT}/Production/api/v2.0/companies"
    session = FakeSession([ok([{"id": "1"}], next_link=url)])
    client = make_client(session)
    with pytest.raises(BusinessCentralError, match="repeated"):
        client.list_companies("v2.0")
    assert len(session.calls) == 1


def test_non_json_response_is_rejected() -> None:
    session = FakeSession([FakeResponse(200, payload=ValueError("nope"), text="nope")])
    client = make_client(session)
    with pytest.raises(BusinessCentralError, match="not JSON"):
        client.list_companies("v2.0")


def test_secret_is_absent_from_retry_logs_and_requests(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    session = FakeSession(
        [
            FakeResponse(429, text=SECRET, headers={"Retry-After": "0"}),
            ok([{"id": "1"}]),
        ]
    )
    client = make_client(session, sleep=lambda _seconds: None)
    client.list_companies("v2.0")
    assert SECRET not in caplog.text
    assert SECRET not in repr(client)
    assert SECRET not in repr(session.calls)
    assert "Bearer access-token" not in caplog.text


def test_secret_is_redacted_in_http_error(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    session = FakeSession([FakeResponse(400, text=f"rejected {SECRET}")])
    client = make_client(session)
    with pytest.raises(BusinessCentralError) as excinfo:
        client.list_companies("v2.0")
    rendered = "".join(traceback.format_exception(excinfo.value))
    assert SECRET not in str(excinfo.value)
    assert SECRET not in rendered
    assert SECRET not in caplog.text
    assert "***" in str(excinfo.value)


def test_secret_is_redacted_in_token_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)

    class FakeApp:
        def acquire_token_for_client(self, scopes: list[str]) -> dict[str, str]:
            return {
                "error": "invalid_client",
                "error_description": f"rejected {SECRET}",
            }

    monkeypatch.setattr(
        "src.bc_client.msal.ConfidentialClientApplication",
        lambda **_kwargs: FakeApp(),
    )
    session = FakeSession([ok([{"id": "1"}])])
    client = BusinessCentralClient(
        tenant_id=TENANT,
        client_id="client-id",
        client_secret=SECRET,
        environment="Production",
        session=session,
        sleep=lambda _seconds: None,
    )
    with pytest.raises(BusinessCentralError) as excinfo:
        client.list_companies("v2.0")
    rendered = "".join(traceback.format_exception(excinfo.value))
    assert SECRET not in str(excinfo.value)
    assert SECRET not in rendered
    assert SECRET not in caplog.text
    assert "***" in caplog.text


def test_client_credentials_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    class FakeApp:
        def acquire_token_for_client(self, scopes: list[str]) -> dict[str, str]:
            seen["scopes"] = list(scopes)
            return {"access_token": "access-token"}

    def factory(**kwargs: Any) -> FakeApp:
        seen["kwargs"] = kwargs
        return FakeApp()

    monkeypatch.setattr("src.bc_client.msal.ConfidentialClientApplication", factory)
    session = FakeSession([ok([{"id": "1", "name": "CRONUS"}])])
    client = BusinessCentralClient(
        tenant_id=TENANT,
        client_id="client-id",
        client_secret=SECRET,
        environment="Production",
        session=session,
        sleep=lambda _seconds: None,
    )
    assert client.list_companies("v2.0") == [{"id": "1", "name": "CRONUS"}]
    assert seen["scopes"] == [SCOPE]
    assert seen["kwargs"]["client_credential"] == SECRET
    assert seen["kwargs"]["authority"] == f"https://login.microsoftonline.com/{TENANT}"
    assert SECRET not in repr(session.calls)


def test_missing_configuration_lists_names_only(monkeypatch: pytest.MonkeyPatch) -> None:
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
    with pytest.raises(ConfigurationError) as excinfo:
        BusinessCentralClient.from_env()
    message = str(excinfo.value)
    assert "BC_TENANT_ID" in message
    assert "BC_CLIENT_ID" in message
    assert "BC_CLIENT_SECRET" not in message
    assert SECRET not in message


def test_tenant_id_with_extra_text_is_rejected() -> None:
    raw = "not-a-guid extra label"
    with pytest.raises(ConfigurationError, match="BC_TENANT_ID") as excinfo:
        BusinessCentralClient(
            tenant_id=raw,
            client_id="client-id",
            client_secret=SECRET,
        )
    assert raw not in str(excinfo.value)
    assert SECRET not in str(excinfo.value)


def test_msal_constructor_errors_do_not_leak(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def factory(**kwargs: Any) -> Any:
        raise ValueError(f"bad {kwargs['client_credential']} {kwargs['authority']}")

    monkeypatch.setattr("src.bc_client.msal.ConfidentialClientApplication", factory)
    session = FakeSession([ok([{"id": "1"}])])
    client = BusinessCentralClient(
        tenant_id=TENANT,
        client_id="client-id",
        client_secret=SECRET,
        environment="Production",
        session=session,
        sleep=lambda _seconds: None,
    )
    with pytest.raises(BusinessCentralError) as excinfo:
        client.list_companies("v2.0")
    rendered = "".join(traceback.format_exception(excinfo.value))
    assert SECRET not in str(excinfo.value)
    assert TENANT not in str(excinfo.value)
    assert SECRET not in rendered
    assert TENANT not in rendered


def test_environment_defaults_to_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.bc_client.load_dotenv", lambda *_args, **_kwargs: False)
    monkeypatch.setenv("BC_TENANT_ID", TENANT)
    monkeypatch.setenv("BC_CLIENT_ID", "client-id")
    monkeypatch.setenv("BC_CLIENT_SECRET", SECRET)
    monkeypatch.delenv("BC_ENVIRONMENT", raising=False)
    monkeypatch.delenv("BC_COMPANY", raising=False)
    client = BusinessCentralClient.from_env()
    assert client.environment == "Production"
    assert client.company == ""
    assert SECRET not in repr(client)


def test_company_id_is_redacted() -> None:
    client = make_client(FakeSession([]))
    client.company = COMPANY
    assert COMPANY not in client.redact(f"companies({COMPANY})")
    assert TENANT not in client.redact(TENANT)


def test_metadata_request_is_get_xml() -> None:
    body = f"<edmx>{TENANT}</edmx>"
    session = FakeSession([FakeResponse(200, text=body)])
    client = make_client(session)
    result = client.fetch_metadata("v2.0")
    call = session.calls[0]
    assert call["url"].endswith("/api/v2.0/$metadata")
    assert call["headers"]["Accept"] == "application/xml"
    assert TENANT not in result.body
    assert "***" in result.body


def test_get_collection_keeps_decimal_amounts() -> None:
    body = '{"value":[{"amount":10.5}]}'
    session = FakeSession([FakeResponse(200, {"value": [{"amount": 1.0}]}, text=body)])
    client = make_client(session)
    rows = client.get_collection(
        "v2.0",
        "accounts",
        company_id=COMPANY,
        query={"$top": "1"},
        parse_decimal=True,
    )
    assert rows == [{"amount": Decimal("10.5")}]
    assert session.calls[0]["params"] == {"$top": "1"}
