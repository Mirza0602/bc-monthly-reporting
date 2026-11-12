"""Business Central REST client.

Authentication is OAuth 2.0 client credentials via MSAL. Settings come only
from the environment (.env): BC_TENANT_ID, BC_CLIENT_ID, BC_CLIENT_SECRET,
BC_ENVIRONMENT (default Production), and BC_COMPANY.

The client secret is never written to logs or exception messages.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin

import msal
import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

API_BASE = "https://api.businesscentral.dynamics.com"
SCOPE = "https://api.businesscentral.dynamics.com/.default"
PREFER_HEADER = "odata.maxpagesize=20000"
DEFAULT_TIMEOUT = 60.0
DEFAULT_MAX_ATTEMPTS = 5
INITIAL_BACKOFF = 1.0
BACKOFF_FACTOR = 2.0
MAX_RETRY_SECONDS = 60.0
RETRYABLE_STATUS = frozenset({429, 503})
_TOKEN_FAILED = (
    "Token request failed. Check BC_TENANT_ID, BC_CLIENT_ID, and BC_CLIENT_SECRET."
)
_REQUIRED_ENV = ("BC_TENANT_ID", "BC_CLIENT_ID", "BC_CLIENT_SECRET")
_GUID = re.compile(
    r"^[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)
_BEARER = re.compile(r"Bearer\s+\S+", re.IGNORECASE)


@dataclass(frozen=True)
class FetchResult:
    """One HTTP response, with secrets already removed from body and error text."""

    status_code: int | None
    body: str
    payload: Any
    error: str


class BusinessCentralError(Exception):
    """The Business Central call did not succeed."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class ConfigurationError(BusinessCentralError):
    """Required environment variables are missing."""


def _env_file() -> Path:
    return Path(__file__).resolve().parents[1] / ".env"


class BusinessCentralClient:
    """Read collections from API v2.0 and the Analytics API."""

    def __init__(
        self,
        *,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        environment: str = "Production",
        company: str = "",
        session: Any = None,
        token_provider: Callable[[], str] | None = None,
        sleep: Callable[[float], None] | None = None,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        self.tenant_id = tenant_id.strip()
        self.client_id = client_id.strip()
        self.environment = environment.strip() or "Production"
        self.company = company.strip()
        self._client_secret = client_secret.strip()
        if not self.tenant_id or not self.client_id or not self._client_secret:
            raise ConfigurationError("Tenant id, client id, and client secret are required.")
        if not _GUID.match(self.tenant_id):
            raise ConfigurationError(
                "BC_TENANT_ID must be the directory GUID only, without a label or extra text."
            )
        self._session = session or requests.Session()
        self._token_provider = token_provider
        self._sleep = sleep or time.sleep
        self._app: Any = None
        self.max_attempts = max_attempts
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> BusinessCentralClient:
        """Build a client from .env and the process environment."""
        load_dotenv(_env_file(), override=False)
        missing = [name for name in _REQUIRED_ENV if not os.environ.get(name, "").strip()]
        if missing:
            joined = ", ".join(missing)
            raise ConfigurationError(
                "Missing configuration: "
                f"{joined}. Copy .env.example to .env and set the values there."
            )
        environment = os.environ.get("BC_ENVIRONMENT", "").strip() or "Production"
        return cls(
            tenant_id=os.environ["BC_TENANT_ID"],
            client_id=os.environ["BC_CLIENT_ID"],
            client_secret=os.environ["BC_CLIENT_SECRET"],
            environment=environment,
            company=os.environ.get("BC_COMPANY", ""),
        )

    def __repr__(self) -> str:
        return f"BusinessCentralClient(environment={self.environment!r})"

    def list_companies(self, route: str) -> list[dict[str, Any]]:
        """Return companies for one API route. The route is not company scoped."""
        return self.get_collection(route, "companies")

    def get_collection(
        self,
        route: str,
        entity_set: str,
        *,
        select: Sequence[str] | None = None,
        odata_filter: str | None = None,
        company_id: str | None = None,
        query: Mapping[str, str] | None = None,
        parse_decimal: bool = False,
    ) -> list[dict[str, Any]]:
        """GET every page of one entity set."""
        url: str | None = self._collection_url(route, entity_set, company_id)
        params: dict[str, str] = dict(query or {})
        built = _query_params(select, odata_filter)
        if built:
            params.update(built)
        active: dict[str, str] | None = params or None
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        while url is not None:
            if url in seen:
                raise BusinessCentralError("Paging stopped because @odata.nextLink repeated.")
            seen.add(url)
            current = url
            payload = self._get_json(
                current,
                active,
                route,
                entity_set,
                parse_decimal=parse_decimal,
            )
            active = None
            value = payload.get("value")
            if not isinstance(value, list):
                raise BusinessCentralError(
                    f"Response for {entity_set} on {route} has no value array."
                )
            for item in value:
                if not isinstance(item, dict):
                    raise BusinessCentralError(
                        f"Response for {entity_set} on {route} contains a non-object value."
                    )
                rows.append(dict(item))
            url = _next_link(payload, current)
        return rows

    def _collection_url(self, route: str, entity_set: str, company_id: str | None) -> str:
        _validate_route(route)
        _validate_entity_set(entity_set)
        prefix = (
            f"{API_BASE}/v2.0/{_quote_segment(self.tenant_id)}/"
            f"{_quote_segment(self.environment)}/api/{_quote_path(route)}"
        )
        entity = _quote_segment(entity_set)
        if company_id:
            return f"{prefix}/companies({_odata_key(company_id)})/{entity}"
        return f"{prefix}/{entity}"

    def fetch(
        self,
        route: str,
        entity_set: str,
        *,
        company_id: str | None = None,
        query: dict[str, str] | None = None,
        parse_decimal: bool = False,
    ) -> FetchResult:
        """One GET. HTTP errors are returned, not raised, and no other URL is tried."""
        url = self._collection_url(route, entity_set, company_id)
        return self._fetch_url(url, query, route, entity_set, parse_decimal=parse_decimal)

    def fetch_metadata(self, route: str) -> FetchResult:
        """GET the OData $metadata document for one API route."""
        _validate_route(route)
        url = (
            f"{API_BASE}/v2.0/{_quote_segment(self.tenant_id)}/"
            f"{_quote_segment(self.environment)}/api/{_quote_path(route)}/$metadata"
        )
        return self._fetch_url(url, None, route, "$metadata", accept="application/xml")

    def _fetch_url(
        self,
        url: str,
        params: dict[str, str] | None,
        route: str,
        entity_set: str,
        *,
        accept: str = "application/json",
        parse_decimal: bool = False,
    ) -> FetchResult:
        try:
            response = self._exchange(url, params, route, entity_set, accept=accept)
        except BusinessCentralError as exc:
            return FetchResult(status_code=exc.status_code, body="", payload=None, error=str(exc))
        raw_text = getattr(response, "text", "") or ""
        body = self.redact(raw_text)
        status = int(response.status_code)
        payload = self._decode_payload(response, raw_text, parse_decimal=parse_decimal)
        error = ""
        if status >= 400:
            error = self.redact(_bc_error_message(payload) or _body_excerpt_text(body))
        return FetchResult(status_code=status, body=body, payload=payload, error=error)

    def _get_json(
        self,
        url: str,
        params: dict[str, str] | None,
        route: str,
        entity_set: str,
        parse_decimal: bool = False,
    ) -> dict[str, Any]:
        response = self._exchange(url, params, route, entity_set)
        status = int(response.status_code)
        if status in RETRYABLE_STATUS or status >= 400:
            raise self._http_error(response) from None
        payload = self._payload(response, parse_decimal=parse_decimal)
        if not isinstance(payload, dict):
            raise BusinessCentralError("Business Central returned JSON that is not an object.")
        return payload

    def _exchange(
        self,
        url: str,
        params: dict[str, str] | None,
        route: str,
        entity_set: str,
        *,
        accept: str = "application/json",
    ) -> Any:
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._session.get(
                    url,
                    params=params,
                    headers=self._headers(accept),
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                message = self.redact(f"Connection failed ({type(exc).__name__}).")
                raise BusinessCentralError(message) from None
            status = int(response.status_code)
            retry = status in RETRYABLE_STATUS and attempt < self.max_attempts
            if retry:
                delay = self._retry_delay(response, attempt)
                remaining = self.max_attempts - 1
                logger.warning(
                    "%s",
                    self.redact(
                        f"HTTP {status} while reading {entity_set} on {route}. "
                        f"Retry {attempt} of {remaining} in {delay:g} seconds."
                    ),
                )
                self._sleep(delay)
                continue
            return response
        raise BusinessCentralError("Request failed.")

    def _headers(self, accept: str = "application/json") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token()}",
            "Accept": accept,
            "Prefer": PREFER_HEADER,
        }

    def _access_token(self) -> str:
        if self._token_provider is not None:
            token = self._token_provider()
        else:
            try:
                result = self._application().acquire_token_for_client(scopes=[SCOPE])
            except (ValueError, OSError):
                raise BusinessCentralError(_TOKEN_FAILED) from None
            token = self._token_from_result(result)
        if not isinstance(token, str) or not token.strip():
            raise BusinessCentralError("Token request failed.")
        return token

    def _application(self) -> Any:
        if self._app is None:
            try:
                self._app = msal.ConfidentialClientApplication(
                    client_id=self.client_id,
                    authority=f"https://login.microsoftonline.com/{self.tenant_id}",
                    client_credential=self._client_secret,
                )
            except (ValueError, OSError):
                raise BusinessCentralError(_TOKEN_FAILED) from None
        return self._app

    def _token_from_result(self, result: Any) -> str:
        if not isinstance(result, dict):
            raise BusinessCentralError("Token request failed.")
        token = result.get("access_token")
        if isinstance(token, str) and token.strip():
            return token
        error = self._redact(str(result.get("error") or "unknown_error"))
        description = self._redact(str(result.get("error_description") or ""))
        message = f"Token request failed ({error})."
        if description:
            message = f"{message} {description}"
        logger.warning("%s", message)
        raise BusinessCentralError(message)

    def _retry_delay(self, response: Any, attempt: int) -> float:
        headers = getattr(response, "headers", None) or {}
        header = headers.get("Retry-After")
        if header is not None:
            try:
                seconds = float(str(header).strip())
            except ValueError:
                seconds = -1.0
            if seconds >= 0:
                return min(seconds, MAX_RETRY_SECONDS)
        delay = INITIAL_BACKOFF * (BACKOFF_FACTOR ** (attempt - 1))
        return min(delay, MAX_RETRY_SECONDS)

    def _http_error(self, response: Any) -> BusinessCentralError:
        status = int(response.status_code)
        excerpt = self._redact(_body_excerpt(response))
        message = f"HTTP {status}."
        if excerpt:
            message = f"{message} {excerpt}"
        return BusinessCentralError(message, status_code=status)

    def _payload(self, response: Any, *, parse_decimal: bool = False) -> Any:
        raw_text = getattr(response, "text", "") or ""
        if parse_decimal:
            if not raw_text:
                raise BusinessCentralError("Business Central returned a response that is not JSON.")
            try:
                return json.loads(raw_text, parse_float=Decimal)
            except ValueError:
                raise BusinessCentralError(
                    "Business Central returned a response that is not JSON."
                ) from None
        decoded = self._decode_payload(response, raw_text, parse_decimal=False)
        if decoded is None:
            raise BusinessCentralError("Business Central returned a response that is not JSON.")
        return decoded

    def _decode_payload(self, response: Any, raw_text: str, *, parse_decimal: bool) -> Any:
        if parse_decimal:
            if not raw_text:
                return None
            try:
                return json.loads(raw_text, parse_float=Decimal)
            except ValueError:
                return None
        try:
            return response.json()
        except ValueError:
            return None

    def redact(self, text: str) -> str:
        """Remove credentials and directory identifiers from text that may be stored or shown."""
        redacted = text
        for secret in (self._client_secret, self.client_id, self.tenant_id, self.company):
            if secret:
                redacted = redacted.replace(secret, "***")
        return _BEARER.sub("Bearer ***", redacted)

    def _redact(self, text: str) -> str:
        return self.redact(text)


def _query_params(
    select: Sequence[str] | None,
    odata_filter: str | None,
) -> dict[str, str] | None:
    params: dict[str, str] = {}
    if select:
        params["$select"] = ",".join(select)
    if odata_filter:
        params["$filter"] = odata_filter
    return params or None


def _next_link(payload: Mapping[str, Any], current_url: str) -> str | None:
    link = payload.get("@odata.nextLink")
    if link is None:
        return None
    if not isinstance(link, str) or not link.strip():
        raise BusinessCentralError("The @odata.nextLink value is not a URL.")
    return urljoin(current_url, link.strip())


def _quote_segment(value: str) -> str:
    return quote(value, safe="")


def _quote_path(path: str) -> str:
    return "/".join(_quote_segment(part) for part in path.split("/"))


def _validate_route(route: str) -> None:
    parts = route.split("/")
    invalid = (
        not route
        or route.startswith("/")
        or route.endswith("/")
        or any(part in {"", ".", ".."} for part in parts)
    )
    if invalid:
        raise BusinessCentralError("Invalid API route.")


def _validate_entity_set(entity_set: str) -> None:
    if not entity_set or "/" in entity_set or entity_set in {".", ".."}:
        raise BusinessCentralError("Invalid entity set.")


def _odata_key(value: str) -> str:
    if _GUID.match(value):
        return value
    escaped = value.replace("'", "''")
    return f"'{escaped}'"


def _body_excerpt(response: Any) -> str:
    text = getattr(response, "text", "") or ""
    if not isinstance(text, str):
        return ""
    return _body_excerpt_text(text)


def _body_excerpt_text(text: str) -> str:
    return " ".join(text.split())[:500]


def _bc_error_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if not isinstance(error, dict):
        return ""
    message = error.get("message")
    if isinstance(message, str):
        return message.strip()
    if isinstance(message, dict):
        value = message.get("value") or message.get("message")
        if isinstance(value, str):
            return value.strip()
    return ""
