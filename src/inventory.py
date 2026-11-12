"""Company probe (AP-00) and the AP-01 data inventory command."""

from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.bc_client import (
    _GUID,
    BusinessCentralClient,
    BusinessCentralError,
    ConfigurationError,
    FetchResult,
)

ROUTE_V2 = "v2.0"
ROUTE_ANALYTICS = "microsoft/analytics/v1.0"
_ENTRY_FIELDS = frozenset({"entity_set", "select", "filter_field", "key"})


class CatalogError(ValueError):
    """config/entities.yaml does not match the expected catalog shape."""


@dataclass(frozen=True)
class Entity:
    """One entity set the extractor is allowed to read."""

    route: str
    entity_set: str
    select: tuple[str, ...]
    filter_field: str | None
    key: str | None


def default_catalog_path() -> Path:
    """Return the catalog path inside this repository."""
    return Path(__file__).resolve().parents[1] / "config" / "entities.yaml"


def load_entity_catalog(path: Path | None = None) -> dict[str, tuple[Entity, ...]]:
    """Load entities grouped by API route."""
    catalog_path = path or default_catalog_path()
    try:
        document = yaml.safe_load(catalog_path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as exc:
        raise CatalogError(str(exc)) from exc
    if not isinstance(document, dict) or set(document) != {ROUTE_V2, ROUTE_ANALYTICS}:
        raise CatalogError(
            "entities.yaml must contain exactly the routes "
            f"{ROUTE_V2!r} and {ROUTE_ANALYTICS!r}."
        )
    return {route: _parse_route(route, document[route]) for route in (ROUTE_V2, ROUTE_ANALYTICS)}


def company_file() -> Path:
    """Gitignored local file for the selected company id. Never .env."""
    return Path(__file__).resolve().parents[1] / ".env.local"


def read_company_id(path: Path | None = None) -> str:
    """Read the company id stored by --probe. The value is not included in errors."""
    file = path or company_file()
    if not file.exists():
        raise ConfigurationError("The company file .env.local is missing. Run --probe first.")
    value = ""
    for line in file.read_text(encoding="utf-8").splitlines():
        if line.startswith("BC_COMPANY="):
            value = line.split("=", 1)[1].strip()
    if not _GUID.match(value):
        raise ConfigurationError(
            "BC_COMPANY in .env.local is missing or not a GUID. Run --probe first."
        )
    return value


def probe_directory() -> Path:
    """Gitignored folder for raw probe responses."""
    return Path(__file__).resolve().parents[1] / "data" / "probe"


def run_probe(catalog_path: Path | None = None) -> int:
    """List companies, select CRONUS DE, and GET each entity once."""
    path = catalog_path or default_catalog_path()
    try:
        catalog = load_entity_catalog(path)
    except (OSError, CatalogError) as exc:
        print(f"ERROR: Could not read {path.name}. {exc}", file=sys.stderr)
        return 1

    v2_count = len(catalog[ROUTE_V2])
    analytics_count = len(catalog[ROUTE_ANALYTICS])
    print(
        f"Catalog: {v2_count} entities on {ROUTE_V2}, "
        f"{analytics_count} entities on {ROUTE_ANALYTICS}."
    )

    try:
        client = BusinessCentralClient.from_env()
    except ConfigurationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not client.company:
        print("BC_COMPANY is empty. A matching company id is stored only in .env.local.")

    failures: list[str] = []
    found: list[tuple[str, dict[str, Any]]] = []
    for route in (ROUTE_V2, ROUTE_ANALYTICS):
        result = client.fetch(route, "companies")
        _save_raw(route, "companies", result)
        if result.status_code != 200 or not isinstance(result.payload, dict):
            detail = result.error or f"HTTP {result.status_code}."
            failure = _route_failure(
                route,
                BusinessCentralError(detail, status_code=result.status_code),
            )
            failures.append(failure)
            if result.error:
                label = _api_label(route)
                print(
                    f"{label} companies HTTP {result.status_code}: {result.error}",
                    file=sys.stderr,
                )
            continue
        companies = result.payload.get("value")
        if not isinstance(companies, list) or not companies:
            failures.append(_empty_failure(route))
            continue
        print(f"{route}: {len(companies)} {'company' if len(companies) == 1 else 'companies'}")
        for company in companies:
            if not isinstance(company, dict):
                continue
            print(_company_line(company))
            if _is_cronus_de(company):
                found.append((route, company))

    if failures:
        for message in failures:
            print(message, file=sys.stderr)

    selected = _select_company(found)
    if selected is None:
        print("ERROR: No company whose name contains CRONUS DE.", file=sys.stderr)
        return 1
    company_id = _text(selected.get("id")) or _text(selected.get("systemId"))
    if not company_id:
        print("ERROR: Selected company has no id.", file=sys.stderr)
        return 1
    _write_company_id(company_file(), company_id)
    print(f"Selected company: {_company_name(selected)}")
    print("Company id stored in .env.local.")
    rows: list[ProbeRow] = []
    for route, entities in catalog.items():
        for entity in entities:
            rows.append(_probe_entity(client, route, entity.entity_set, company_id))

    _print_table(rows)
    for row in rows:
        if row.error:
            status = "none" if row.status is None else str(row.status)
            print(
                f"{row.entity_set} {_api_label(row.route)} HTTP {status}: {row.error}",
                file=sys.stderr,
            )
    if failures or any(row.status != 200 for row in rows):
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Command line entry point for the company probe and the AP-01 inventory."""
    parser = argparse.ArgumentParser(
        description="Probe Business Central and build the AP-01 field inventory and data profile."
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="List companies from API v2.0 and microsoft/analytics/v1.0.",
    )
    parser.add_argument(
        "--datenbestand",
        action="store_true",
        help="Write Feldinventar.md, the snapshot, and Datenprofil.md.",
    )
    parser.add_argument(
        "--stichtag",
        default=None,
        help="Cutoff date YYYY-MM-DD. Default: last day of the previous month.",
    )
    args = parser.parse_args(argv)
    if args.stichtag and not args.datenbestand:
        print("ERROR: --stichtag belongs to --datenbestand.", file=sys.stderr)
        return 2
    if args.probe and args.datenbestand:
        print("ERROR: Use either --probe or --datenbestand.", file=sys.stderr)
        return 2
    if not args.probe and not args.datenbestand:
        print(
            "Use --probe or --datenbestand.",
            file=sys.stderr,
        )
        return 2
    _configure_stdio()
    if args.datenbestand:
        from src.datenbestand_run import run_datenbestand

        return run_datenbestand(args.stichtag)
    return run_probe()


def _parse_route(route: str, entries: Any) -> tuple[Entity, ...]:
    if not isinstance(entries, list) or not entries:
        raise CatalogError(f"Route {route} has no entities.")
    seen: set[str] = set()
    parsed: list[Entity] = []
    for entry in entries:
        entity = _parse_entity(route, entry)
        if entity.entity_set in seen:
            raise CatalogError(f"Duplicate entity set {entity.entity_set!r} on route {route}.")
        seen.add(entity.entity_set)
        parsed.append(entity)
    return tuple(parsed)


def _parse_entity(route: str, entry: Any) -> Entity:
    if not isinstance(entry, dict) or set(entry) != _ENTRY_FIELDS:
        missing = [] if not isinstance(entry, dict) else sorted(_ENTRY_FIELDS - set(entry))
        extra = [] if not isinstance(entry, dict) else sorted(set(entry) - _ENTRY_FIELDS)
        raise CatalogError(f"Entity on {route} has missing={missing} extra={extra}.")
    entity_set = entry["entity_set"]
    if not isinstance(entity_set, str) or not entity_set.strip():
        raise CatalogError(f"Entity on {route} needs an entity_set name.")
    entity_set = entity_set.strip()
    columns = _parse_select(entity_set, entry["select"])
    key = _optional_name(entry["key"], f"{entity_set} key")
    filter_field = _optional_name(entry["filter_field"], f"{entity_set} filter_field")
    if key is not None and key not in columns:
        raise CatalogError(f"{entity_set}: key {key!r} is not in select.")
    if filter_field is not None and filter_field not in columns:
        raise CatalogError(f"{entity_set}: filter_field {filter_field!r} is not in select.")
    return Entity(
        route=route,
        entity_set=entity_set,
        select=tuple(columns),
        filter_field=filter_field,
        key=key,
    )


def _parse_select(entity_set: str, raw_select: Any) -> list[str]:
    if not isinstance(raw_select, list) or not raw_select:
        raise CatalogError(f"{entity_set}: select must be a non-empty list.")
    columns: list[str] = []
    for column in raw_select:
        if not isinstance(column, str) or not column.strip():
            raise CatalogError(f"{entity_set}: select entries must be strings.")
        columns.append(column.strip())
    if len(columns) != len(set(columns)):
        raise CatalogError(f"{entity_set}: select contains duplicates.")
    return columns


def _optional_name(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise CatalogError(f"{label} must be a string or null.")


def _route_failure(route: str, exc: BusinessCentralError) -> str:
    if route == ROUTE_ANALYTICS:
        return f"ERROR: Analytics route {ROUTE_ANALYTICS} did not respond: {exc}"
    return f"ERROR: Route {route} did not return a company list: {exc}"


def _empty_failure(route: str) -> str:
    if route != ROUTE_ANALYTICS:
        return f"ERROR: Route {route} responded with no companies."
    return (
        "ERROR: Analytics route microsoft/analytics/v1.0 responded with no companies. "
        "Install the Power BI Connector app in Business Central (Extension Management) "
        "and run the probe again."
    )


def _company_line(row: dict[str, Any]) -> str:
    return f"- {_company_name(row) or '(no name)'}"


def _company_name(row: dict[str, Any]) -> str:
    return _text(row.get("displayName")) or _text(row.get("name"))


def _is_cronus_de(row: dict[str, Any]) -> bool:
    return "cronus de" in _company_name(row).casefold()


def _select_company(found: list[tuple[str, dict[str, Any]]]) -> dict[str, Any] | None:
    for route, company in found:
        if route == ROUTE_V2:
            return company
    if found:
        return found[0][1]
    return None


def _write_company_id(path: Path, company_id: str) -> None:
    existing: list[str] = []
    if path.exists():
        existing = path.read_text(encoding="utf-8").splitlines()
    lines: list[str] = []
    replaced = False
    for line in existing:
        if line.startswith("BC_COMPANY="):
            lines.append(f"BC_COMPANY={company_id}")
            replaced = True
        else:
            lines.append(line)
    if not replaced:
        lines.append(f"BC_COMPANY={company_id}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


@dataclass(frozen=True)
class ProbeRow:
    route: str
    entity_set: str
    status: int | None
    fields: int | None
    total: int | None
    seconds: float
    error: str


def _probe_entity(
    client: BusinessCentralClient,
    route: str,
    entity_set: str,
    company_id: str,
) -> ProbeRow:
    started = time.perf_counter()
    result = client.fetch(
        route,
        entity_set,
        company_id=company_id,
        query={"$top": "1", "$count": "true"},
    )
    _save_raw(route, entity_set, result)
    return ProbeRow(
        route=route,
        entity_set=entity_set,
        status=result.status_code,
        fields=_field_count(result.payload) if result.status_code == 200 else None,
        total=_row_count(result.payload) if result.status_code == 200 else None,
        seconds=time.perf_counter() - started,
        error=result.error,
    )


def _save_raw(route: str, entity_set: str, result: FetchResult) -> None:
    folder = probe_directory()
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{_file_slug(route)}__{_file_slug(entity_set)}.json"
    folder.joinpath(name).write_text(result.body, encoding="utf-8")


def _file_slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")


def _field_count(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("value")
    if not isinstance(value, list):
        return None
    if not value:
        return 0
    first = value[0]
    if not isinstance(first, dict):
        return None
    return sum(1 for key in first if not str(key).startswith("@"))


def _row_count(payload: Any) -> int | None:
    if not isinstance(payload, dict) or "@odata.count" not in payload:
        return None
    raw = payload["@odata.count"]
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def _print_table(rows: list[ProbeRow]) -> None:
    records = [
        ("Entity", "API", "HTTP", "Fields", "Rows", "Seconds"),
        *[
            (
                row.entity_set,
                _api_label(row.route),
                "" if row.status is None else str(row.status),
                "" if row.fields is None else str(row.fields),
                "" if row.total is None else str(row.total),
                f"{row.seconds:.2f}",
            )
            for row in rows
        ],
    ]
    widths = [max(len(record[index]) for record in records) for index in range(6)]
    for record in records:
        print("  ".join(part.ljust(widths[index]) for index, part in enumerate(record)))


def _api_label(route: str) -> str:
    if route == ROUTE_ANALYTICS:
        return "Analytics"
    return route


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            continue


if __name__ == "__main__":
    raise SystemExit(main())
