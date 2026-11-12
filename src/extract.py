"""Load the reporting entities into one snapshot folder.

The cutoff is stored in manifest.json and is not applied as a row filter.
Analytics dimensionSetEntries is not read. dynamicDimensions, joined later on
dimensionSetID, is the source for the dimension-set table. v2.0
dimensionSetLines is an optional counter-test and is not part of the standard
run. trialBalances is loaded by month in src.trial_balance.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from src.bc_client import BusinessCentralClient, BusinessCentralError
from src.datenbestand import (
    fmt_date,
    parse_stichtag,
    scan_tree,
    write_manifest,
    write_snapshot_table,
)
from src.inventory import (
    ROUTE_ANALYTICS,
    ROUTE_V2,
    CatalogError,
    ConfigurationError,
    Entity,
    load_entity_catalog,
    read_company_id,
)
from src.trial_balance import (
    CheckResult,
    build_checks,
    checks_document,
    fetch_periods,
    load_periods,
    money,
    sanitize_record,
    trial_columns,
)

EXCLUDED = frozenset(
    {
        (ROUTE_ANALYTICS, "dimensionSetEntries"),
        (ROUTE_V2, "trialBalances"),
    }
)
DYNAMIC_COLUMNS = (
    "dimensionSetID",
    "customDimensionCode",
    "customDimensionName",
    "customDimensionValueCode",
    "customDimensionValueName",
    "globalDimensionNo",
)


@dataclass(frozen=True)
class PlannedEntity:
    route: str
    entity_set: str
    columns: tuple[str, ...]
    kind: str


@dataclass(frozen=True)
class FetchRecord:
    route: str
    entity: str
    rows: list[dict[str, Any]]
    columns: tuple[str, ...]
    fetched_at: str
    seconds: float


def entity_plan(catalog: Mapping[str, Sequence[Entity]]) -> tuple[PlannedEntity, ...]:
    """Catalog entities, then dynamicDimensions, then the monthly trial balance."""
    planned: list[PlannedEntity] = []
    for route, entities in catalog.items():
        for entity in entities:
            if (route, entity.entity_set) in EXCLUDED:
                continue
            planned.append(PlannedEntity(route, entity.entity_set, entity.select, "catalog"))
    planned.append(
        PlannedEntity(ROUTE_ANALYTICS, "dynamicDimensions", DYNAMIC_COLUMNS, "dimensions")
    )
    trial = _trial_entity(catalog)
    planned.append(PlannedEntity(ROUTE_V2, "trialBalances", trial_columns(trial.select), "trial"))
    return tuple(planned)


def snapshot_stem(route: str, entity_set: str) -> str:
    prefix = "v2" if route == ROUTE_V2 else "analytics"
    return f"{prefix}__{entity_set}"


def run_extract(
    as_of: date,
    *,
    expand_dimensions: bool = False,
    run_day: date | None = None,
) -> int:
    """Read every planned entity and replace the snapshot folder for run_day."""
    run_day = run_day or date.today()
    print(
        f"Stichtag {as_of.isoformat()}. Snapshot {run_day.isoformat()}. "
        "Rows are not filtered by the cutoff."
    )
    try:
        catalog = load_entity_catalog()
        client = BusinessCentralClient.from_env()
        company_id = read_company_id()
    except (OSError, CatalogError, ConfigurationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    client.company = company_id
    needles = _needles(client, company_id)
    records: list[FetchRecord] = []
    try:
        for planned in entity_plan(catalog):
            print(f"Reading {planned.entity_set}.", flush=True)
            records.append(_fetch_planned(client, company_id, planned, as_of))
        if expand_dimensions:
            _print_dimension_countertest(client, company_id)
    except BusinessCentralError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    checks = _checks(records, as_of)
    folder = _repo_root() / "data" / "snapshots" / run_day.isoformat()
    try:
        _publish(folder, records, as_of, run_day, client.environment, checks, needles)
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    _print_checks(checks)
    print(f"Snapshot {folder.relative_to(_repo_root())}.")
    return 1 if checks.failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load Business Central entities into data/snapshots/<run date>."
    )
    parser.add_argument(
        "--stichtag",
        default=None,
        help="Cutoff YYYY-MM-DD. Default: last day of the previous month. Not a row filter.",
    )
    parser.add_argument(
        "--expand-dimensions",
        action="store_true",
        help="Optional v2.0 dimensionSetLines counter-test. The rows are not written.",
    )
    args = parser.parse_args(argv)
    _configure_stdio()
    try:
        as_of = parse_stichtag(args.stichtag)
    except ValueError:
        print("ERROR: --stichtag must be YYYY-MM-DD.", file=sys.stderr)
        return 2
    return run_extract(as_of, expand_dimensions=args.expand_dimensions)


def _fetch_planned(
    client: BusinessCentralClient,
    company_id: str,
    planned: PlannedEntity,
    as_of: date,
) -> FetchRecord:
    if planned.kind == "trial":
        rows, seconds, fetched_at = fetch_periods(client, company_id, as_of, planned.columns)
        print(f"{planned.entity_set}: {len(rows)} rows in {seconds:.1f}s", flush=True)
        return FetchRecord(
            planned.route, planned.entity_set, rows, planned.columns, fetched_at, seconds
        )
    fetched_at = _now()
    started = time.perf_counter()
    rows = _load_collection(client, company_id, planned)
    seconds = round(time.perf_counter() - started, 3)
    cleaned = [sanitize_record(row) for row in rows]
    print(f"{planned.entity_set}: {len(cleaned)} rows in {seconds:.1f}s", flush=True)
    return FetchRecord(
        planned.route, planned.entity_set, cleaned, planned.columns, fetched_at, seconds
    )


def _load_collection(
    client: BusinessCentralClient,
    company_id: str,
    planned: PlannedEntity,
) -> list[dict[str, Any]]:
    try:
        return client.get_collection(
            planned.route,
            planned.entity_set,
            select=planned.columns,
            company_id=company_id,
            parse_decimal=True,
        )
    except BusinessCentralError as exc:
        if planned.kind != "dimensions" or exc.status_code != 400:
            raise
        print(f"{planned.entity_set}: $select was rejected. Loading without $select.")
        return client.get_collection(
            planned.route,
            planned.entity_set,
            company_id=company_id,
            parse_decimal=True,
        )


def fetch_dimension_set_lines(
    client: BusinessCentralClient,
    company_id: str,
) -> list[dict[str, Any]]:
    """Optional counter-test. The standard run does not call this."""
    previous = client.timeout
    client.timeout = max(previous, 240.0)
    try:
        return client.get_collection(
            ROUTE_V2,
            "generalLedgerEntries",
            company_id=company_id,
            query={"$expand": "dimensionSetLines"},
            parse_decimal=True,
        )
    finally:
        client.timeout = previous


def _print_dimension_countertest(client: BusinessCentralClient, company_id: str) -> None:
    rows = fetch_dimension_set_lines(client, company_id)
    with_lines = 0
    for row in rows:
        lines = row.get("dimensionSetLines")
        if isinstance(lines, list) and lines:
            with_lines += 1
    print(
        f"dimensionSetLines counter-test: {len(rows)} entries, "
        f"{with_lines} with lines. Not written."
    )


def _checks(records: Sequence[FetchRecord], as_of: date) -> CheckResult:
    gl_rows = _record(records, "generalLedgerEntries").rows
    income_rows = len(_record(records, "incomeStatementGeneralLedgerEntries").rows)
    balance_rows = len(_record(records, "balanceSheetGeneralLedgerEntries").rows)
    trial_rows = _record(records, "trialBalances").rows
    return build_checks(
        as_of=as_of,
        gl_rows=gl_rows,
        income_rows=income_rows,
        balance_rows=balance_rows,
        trial_rows=trial_rows,
    )


def _publish(
    folder: Path,
    records: Sequence[FetchRecord],
    as_of: date,
    run_day: date,
    environment: str,
    checks: CheckResult,
    needles: Sequence[str],
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    written_names: list[str] = []
    entities: list[dict[str, Any]] = []
    periods = load_periods(as_of)
    for record in records:
        written = write_snapshot_table(
            folder,
            snapshot_stem(record.route, record.entity),
            record.rows,
            record.columns,
        )
        written_names.extend((written["parquet"], written["csvSample"]))
        entry: dict[str, Any] = {
            "entity": record.entity,
            "route": record.route,
            "rows": written["rows"],
            "fetchedAt": record.fetched_at,
            "seconds": record.seconds,
            "parquet": written["parquet"],
            "csvSample": written["csvSample"],
        }
        if record.entity == "trialBalances":
            entry["periods"] = len(periods)
            entry["periodStart"] = periods[0][0].isoformat()
            entry["periodEnd"] = periods[-1][1].isoformat()
        entities.append(entry)
    document = {
        "stand": fmt_date(run_day),
        "runDate": run_day.isoformat(),
        "stichtag": as_of.isoformat(),
        "environment": _environment_name(environment),
        "entities": entities,
        "checks": checks_document(checks),
    }
    write_manifest(folder, document, needles)
    written_names.append("manifest.json")
    kept = {folder / name for name in written_names}
    _assert_clean(kept, needles)
    for path in folder.iterdir():
        if path.is_file() and path not in kept:
            path.unlink()
    _assert_clean([path for path in folder.iterdir() if path.is_file()], needles)
    scan_tree(folder, needles)


def _assert_clean(paths: Sequence[Path], needles: Sequence[str]) -> None:
    for path in paths:
        blob = path.read_bytes()
        lowered = blob.lower()
        if b"businesscentral.dynamics.com" in lowered or b"login.microsoftonline.com" in lowered:
            raise RuntimeError("A snapshot file contains an environment URL.")
        if b"@odata.context" in lowered or b"@odata.nextlink" in lowered:
            raise RuntimeError("A snapshot file contains an OData context URL.")
        for needle in needles:
            if needle and needle.encode("utf-8") in blob:
                raise RuntimeError("A snapshot file contains a forbidden identifier.")


def _environment_name(environment: str) -> str:
    if "://" in environment or "businesscentral.dynamics.com" in environment.casefold():
        return ""
    return environment


def _record(records: Sequence[FetchRecord], entity: str) -> FetchRecord:
    for record in records:
        if record.entity == entity:
            return record
    raise RuntimeError(f"Missing entity {entity}.")


def _trial_entity(catalog: Mapping[str, Sequence[Entity]]) -> Entity:
    for entity in catalog[ROUTE_V2]:
        if entity.entity_set == "trialBalances":
            return entity
    raise CatalogError("trialBalances is missing from the catalog.")


def _needles(client: BusinessCentralClient, company_id: str) -> tuple[str, ...]:
    values = (client.tenant_id, client.client_id, client._client_secret, company_id)
    unique = list(dict.fromkeys(value for value in values if value))
    return tuple(unique)


def _print_checks(result: CheckResult) -> None:
    print(f"P1 {money(result.p1)}.")
    print(
        "GL rows "
        f"income {result.income_rows}, balance {result.balance_rows}, "
        f"v2 {result.v2_rows}, gap {result.population_gap}."
    )
    print(f"Movement diffs {len(result.movement)}.")
    for item in result.movement[:50]:
        print(f"movement {item.account} {item.period_end.isoformat()} {money(item.difference)}")
    print(f"Balance diffs {len(result.balance)}.")
    for item in result.balance[:50]:
        print(f"balance {item.account} {money(item.difference)}")


def _now() -> str:
    from datetime import datetime

    return datetime.now().astimezone().isoformat(timespec="seconds")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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
