"""HTTP orchestration for AP-01. Calculations live in datenbestand.py."""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from src.bc_client import BusinessCentralClient, BusinessCentralError, ConfigurationError
from src.datenbestand import (
    AccountInfo,
    DetailRow,
    DimensionMaster,
    FilterProbe,
    GlRow,
    JoinStats,
    MetadataModel,
    RouteAssessment,
    SetIdStats,
    ShortcutSlot,
    TrialRow,
    assert_no_secrets,
    build_profile,
    category_label,
    classify_dimensions,
    compare_trial,
    count_covered,
    fmt_date,
    fmt_seconds,
    join_stats,
    norm_key,
    open_at,
    parse_amount,
    parse_iso_date,
    parse_metadata,
    parse_stichtag,
    readable_token,
    render_feldinventar,
    render_profile,
    sign_check,
    trial_dates,
)
from src.inventory import (
    ROUTE_ANALYTICS,
    ROUTE_V2,
    Entity,
    load_entity_catalog,
    read_company_id,
)

SAMPLE_TOP = 50
SAMPLE_LIMIT_SECONDS = 60.0
FULL_TIMEOUT_SECONDS = 240.0


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run_datenbestand(stichtag: str | None = None) -> int:
    """Fetch metadata, test dimension routes, snapshot core entities, write the reports."""
    try:
        as_of = parse_stichtag(stichtag)
    except ValueError:
        print("ERROR: --stichtag must be YYYY-MM-DD.", file=sys.stderr)
        return 2
    run_day = date.today()
    print(f"Stichtag {fmt_date(as_of)}. Snapshot date {run_day.isoformat()}.")
    try:
        return _run(as_of, run_day)
    except ConfigurationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except BusinessCentralError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _run(as_of: date, run_day: date) -> int:
    catalog = load_entity_catalog()
    client = BusinessCentralClient.from_env()
    company_id = read_company_id()
    client.company = company_id
    needles = _needles(client, company_id)
    raw_dir = repo_root() / "data" / "raw" / run_day.isoformat()
    probe_dir = repo_root() / "data" / "probe" / "ap01"

    print("Reading $metadata.")
    models = {
        ROUTE_V2: _metadata(client, ROUTE_V2, probe_dir / "metadata_v2.xml"),
        ROUTE_ANALYTICS: _metadata(
            client, ROUTE_ANALYTICS, probe_dir / "metadata_analytics.xml"
        ),
    }
    catalog_rows = [
        (entity.route, entity.entity_set, entity.key)
        for entities in catalog.values()
        for entity in entities
    ]
    field_text = render_feldinventar(catalog_rows, models, run_day)
    assert_no_secrets(field_text, needles)
    field_path = repo_root() / "docs" / "spec" / "Feldinventar.md"
    field_path.write_text(field_text, encoding="utf-8")
    print(f"Wrote {field_path.relative_to(repo_root())}.")

    loaded = _load_core(client, catalog, company_id)
    masters, department_values, group_values = _masters(
        loaded[(ROUTE_V2, "dimensions")],
        loaded[(ROUTE_V2, "dimensionValues")],
    )
    departments, groups = classify_dimensions(masters)
    print(
        "Dimensions: "
        + ", ".join(f"{item.code} ({item.value_count})" for item in masters)
    )

    gl_rows, analytics_sets = _gl_rows(loaded)
    accounts, category_source = _accounts(
        loaded[(ROUTE_V2, "accounts")],
        loaded[(ROUTE_ANALYTICS, "generalLedgerAccounts")],
        loaded[(ROUTE_ANALYTICS, "generalLedgerAccountCategories")],
    )
    print(f"Category source: {category_source}. Accounts: {len(accounts)}.")
    seen_categories = sorted({account.category for account in accounts if account.category})
    print("Categories: " + ", ".join(seen_categories))

    routes, join, set_ids, filters, shortcuts = _dimension_routes(
        client,
        company_id,
        models[ROUTE_V2],
        models[ROUTE_ANALYTICS],
        loaded,
        gl_rows,
        analytics_sets,
        departments,
        groups,
        raw_dir,
    )

    budget_rows = _count(client, ROUTE_ANALYTICS, "generalLedgerBudgets", company_id)
    budget_entries = _count(client, ROUTE_ANALYTICS, "generalLedgerBudgetEntries", company_id)
    closing_rows = _count(client, ROUTE_ANALYTICS, "closingGeneralLedgerEntries", company_id)
    print(
        f"Budgets {budget_rows}, budget entries {budget_entries}, closing entries {closing_rows}."
    )

    trials, trial_error = _trial_balances(
        client,
        _entity(catalog, ROUTE_V2, "trialBalances"),
        company_id,
        as_of,
    )
    account_map = {account.number: account for account in accounts}
    comparisons = tuple(
        compare_trial(gl_rows, mapped, account_map, day) for day, _raw, mapped in trials
    )

    v2_amounts = [
        (
            norm_key(row.get("entryNumber")),
            parse_amount(row.get("debitAmount")),
            parse_amount(row.get("creditAmount")),
        )
        for row in loaded[(ROUTE_V2, "generalLedgerEntries")]
    ]
    checked = sign_check([(row.entry_no, row.amount) for row in gl_rows], v2_amounts)
    customer_rows = loaded[(ROUTE_ANALYTICS, "customerLedgerEntries")]
    vendor_rows = loaded[(ROUTE_ANALYTICS, "vendorLedgerEntries")]
    customers = open_at(_customer_details(customer_rows), as_of)
    vendors = open_at(_vendor_details(vendor_rows), as_of)

    profile = build_profile(
        stand=run_day,
        as_of=as_of,
        run_day=run_day,
        gl_rows=gl_rows,
        accounts=accounts,
        customers=customers,
        vendors=vendors,
        routes=routes,
        masters=masters,
        department_values=department_values,
        customer_group_values=group_values,
        join=join,
        set_ids=set_ids,
        filter_probes=filters,
        shortcuts=shortcuts,
        trials=comparisons,
        trial_error=trial_error,
        budget_rows=budget_rows,
        budget_entry_rows=budget_entries,
        closing_rows=closing_rows,
        sign=checked,
        category_source=category_source,
        dimension_entity_sets=_dimension_entity_sets(models),
    )
    profile_text = render_profile(profile)
    assert_no_secrets(profile_text, needles)
    profile_path = repo_root() / "docs" / "spec" / "Datenprofil.md"
    profile_path.write_text(profile_text, encoding="utf-8")

    print(f"Wrote {profile_path.relative_to(repo_root())}.")
    print("The snapshot is written by python -m src.extract.")
    print(f"Recommendation: {profile.recommendation_key or 'none'}.")
    if profile.years:
        balance = sum((row.balance for row in profile.years), start=0)
        print(f"GL balance {balance}.")
    print(f"Open customers {profile.customers.entries}, vendors {profile.vendors.entries}.")
    return 0


def _metadata(client: BusinessCentralClient, route: str, path: Path) -> MetadataModel:
    result = client.fetch_metadata(route)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.body, encoding="utf-8")
    if result.status_code != 200 or not result.body.lstrip().startswith("<"):
        detail = result.error or f"HTTP {result.status_code}."
        raise BusinessCentralError(f"$metadata for {route} failed. {detail}")
    return parse_metadata(result.body)


def _load_core(
    client: BusinessCentralClient,
    catalog: Mapping[str, tuple[Entity, ...]],
    company_id: str,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    names = (
        (ROUTE_ANALYTICS, "incomeStatementGeneralLedgerEntries"),
        (ROUTE_ANALYTICS, "balanceSheetGeneralLedgerEntries"),
        (ROUTE_ANALYTICS, "generalLedgerAccounts"),
        (ROUTE_ANALYTICS, "generalLedgerAccountCategories"),
        (ROUTE_ANALYTICS, "accountCategories"),
        (ROUTE_ANALYTICS, "dimensions"),
        (ROUTE_ANALYTICS, "dimensionSetEntries"),
        (ROUTE_ANALYTICS, "customerLedgerEntries"),
        (ROUTE_ANALYTICS, "vendorLedgerEntries"),
        (ROUTE_ANALYTICS, "itemValueEntries"),
        (ROUTE_ANALYTICS, "items"),
        (ROUTE_ANALYTICS, "customers"),
        (ROUTE_ANALYTICS, "vendors"),
        (ROUTE_V2, "accounts"),
        (ROUTE_V2, "dimensions"),
        (ROUTE_V2, "dimensionValues"),
        (ROUTE_V2, "generalLedgerEntries"),
    )
    loaded: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for route, name in names:
        entity = _entity(catalog, route, name)
        started = time.perf_counter()
        rows = client.get_collection(
            route,
            name,
            select=entity.select,
            company_id=company_id,
            parse_decimal=True,
        )
        seconds = time.perf_counter() - started
        loaded[(route, name)] = rows
        print(f"{name}: {len(rows)} rows in {seconds:.1f}s")
    _require(
        loaded[(ROUTE_ANALYTICS, "incomeStatementGeneralLedgerEntries")],
        "accountNo",
        "postingDate",
        "amount",
        "entryNo",
        "dimensionSetID",
    )
    _require(
        loaded[(ROUTE_ANALYTICS, "balanceSheetGeneralLedgerEntries")],
        "glAccountNo",
        "postingDate",
        "amount",
        "entryNo",
        "dimensionSetID",
    )
    _require(
        loaded[(ROUTE_V2, "generalLedgerEntries")],
        "entryNumber",
        "debitAmount",
        "creditAmount",
    )
    _require(
        loaded[(ROUTE_ANALYTICS, "customerLedgerEntries")],
        "cleEntryNo",
        "dclePostingDate",
        "dcleAmountLCY",
        "dcleCustomerNo",
    )
    _require(
        loaded[(ROUTE_ANALYTICS, "vendorLedgerEntries")],
        "vleEntryNo",
        "dvlePostingDate",
        "dvleAmountLCY",
        "dvleVendorNo",
    )
    return loaded


def _gl_rows(
    loaded: Mapping[tuple[str, str], list[dict[str, Any]]],
) -> tuple[list[GlRow], list[tuple[str, str]]]:
    rows: list[GlRow] = []
    sets: list[tuple[str, str]] = []
    specs = (
        (ROUTE_ANALYTICS, "incomeStatementGeneralLedgerEntries", "guv", "accountNo"),
        (ROUTE_ANALYTICS, "balanceSheetGeneralLedgerEntries", "bilanz", "glAccountNo"),
    )
    for route, name, ledger, account_field in specs:
        for item in loaded[(route, name)]:
            entry_no = norm_key(item.get("entryNo"))
            rows.append(
                GlRow(
                    posting_date=parse_iso_date(item.get("postingDate")),
                    amount=parse_amount(item.get("amount")),
                    account=norm_key(item.get(account_field)),
                    ledger=ledger,
                    entry_no=entry_no,
                )
            )
            sets.append((entry_no, norm_key(item.get("dimensionSetID"))))
    return rows, sets


def _accounts(
    v2_rows: Sequence[Mapping[str, Any]],
    analytics_rows: Sequence[Mapping[str, Any]],
    category_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[AccountInfo], str]:
    analytics_categories = _analytics_categories(analytics_rows, category_rows)
    infos: list[AccountInfo] = []
    seen: set[str] = set()
    for row in v2_rows:
        number = norm_key(row.get("number"))
        if not number or number in seen:
            continue
        seen.add(number)
        infos.append(
            AccountInfo(
                number=number,
                name=str(row.get("displayName") or "").strip(),
                category=category_label(row.get("category")),
                subcategory=readable_token(row.get("subCategory")),
                analytics_category=category_label(analytics_categories.get(number, "")),
            )
        )
    for row in analytics_rows:
        number = norm_key(row.get("accountNo"))
        if not number or number in seen:
            continue
        seen.add(number)
        infos.append(
            AccountInfo(
                number=number,
                name=str(row.get("accountName") or "").strip(),
                category="",
                subcategory="",
                analytics_category=analytics_categories.get(number, ""),
            )
        )
    filled = sum(1 for info in infos if info.category)
    analytics_filled = sum(1 for info in infos if info.analytics_category)
    if filled == 0 and analytics_filled:
        switched = [
            AccountInfo(
                info.number,
                info.name,
                info.analytics_category,
                info.subcategory,
                info.analytics_category,
            )
            for info in infos
        ]
        return switched, (
            "der Analytics-Kontenkategorie accountCategory, gelesen über "
            "accountSubcategoryEntryNo"
        )
    return infos, (
        "dem Feld category der API v2.0 accounts. "
        "Die API liefert englische Namen. Income steht hier als Einnahmen, "
        "Cost of Goods Sold als Wareneinsatz, Expense als Ausgaben, "
        "Assets als Anlagen, Liabilities als Verbindlichkeiten und Equity als Eigenkapital"
    )


def _analytics_categories(
    accounts: Sequence[Mapping[str, Any]],
    categories: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    nodes = {norm_key(row.get("entryNo")): row for row in categories}
    found: dict[str, str] = {}
    for account in accounts:
        number = norm_key(account.get("accountNo"))
        current = norm_key(account.get("accountSubcategoryEntryNo"))
        seen: set[str] = set()
        label = ""
        while current and current not in {"0"} and current not in seen:
            seen.add(current)
            node = nodes.get(current)
            if node is None:
                break
            bucket = category_label(node.get("accountCategory"))
            description = readable_token(node.get("description"))
            if bucket:
                label = bucket
                break
            if description and not label:
                label = description
            parent = norm_key(node.get("parentEntryNo"))
            current = "" if parent == current else parent
        if number:
            found[number] = label
    return found


def _masters(
    dimensions: Sequence[Mapping[str, Any]],
    values: Sequence[Mapping[str, Any]],
) -> tuple[list[DimensionMaster], tuple[str, ...], tuple[str, ...]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for value in values:
        grouped[str(value.get("dimensionId") or "")].append(value)
    masters: list[DimensionMaster] = []
    department_values: list[str] = []
    group_values: list[str] = []
    for row in dimensions:
        code = str(row.get("code") or "").strip()
        name = str(row.get("displayName") or "").strip()
        pairs = tuple(
            sorted(
                (
                    str(item.get("code") or "").strip(),
                    str(item.get("displayName") or "").strip(),
                )
                for item in grouped.get(str(row.get("id") or ""), [])
            )
        )
        masters.append(DimensionMaster(code, name, len(pairs), ()))
        listed = tuple(f"{value_code} {value_name}".strip() for value_code, value_name in pairs)
        blob = f"{code} {name}"
        if _is_department(blob):
            department_values.extend(listed)
        if _is_group(blob):
            group_values.extend(listed)
    return masters, tuple(department_values), tuple(group_values)


def _dimension_routes(
    client: BusinessCentralClient,
    company_id: str,
    v2_model: MetadataModel,
    analytics_model: MetadataModel,
    loaded: Mapping[tuple[str, str], list[dict[str, Any]]],
    gl_rows: Sequence[GlRow],
    analytics_sets: Sequence[tuple[str, str]],
    departments: Sequence[str],
    groups: Sequence[str],
    raw_dir: Path,
) -> tuple[list[RouteAssessment], JoinStats, SetIdStats, list[FilterProbe], list[ShortcutSlot]]:
    population_keys = [row.entry_no for row in gl_rows]
    v2_rows = loaded[(ROUTE_V2, "generalLedgerEntries")]
    v2_keys = [norm_key(row.get("entryNumber")) for row in v2_rows]
    joined = join_stats(population_keys, v2_keys)

    expand = _expand_route(
        client,
        company_id,
        v2_model,
        population_keys,
        departments,
        groups,
        raw_dir,
    )
    dynamic = _dynamic_route(
        client,
        company_id,
        analytics_model,
        analytics_sets,
        population_keys,
        departments,
        groups,
        raw_dir,
    )
    shortcuts = _shortcuts(loaded[(ROUTE_ANALYTICS, "dimensions")])
    shortcut_route = RouteAssessment(
        key="shortcut",
        works=bool(loaded[(ROUTE_ANALYTICS, "dimensions")]),
        per_entry=False,
        complete=bool(loaded[(ROUTE_ANALYTICS, "dimensions")]),
        http_status=200 if loaded[(ROUTE_ANALYTICS, "dimensions")] else None,
        seconds=None,
        rows=len(loaded[(ROUTE_ANALYTICS, "dimensions")]),
        population=len(population_keys),
        with_department=None,
        with_customer_group=None,
        detail=(
            "Eine Zeile mit den Plätzen dim1 bis dim8. "
            "Das ist die Shortcut-Einrichtung der Firma, kein Wert je Sachposten."
            if loaded[(ROUTE_ANALYTICS, "dimensions")]
            else "Die Entität hat keine Zeile geliefert."
        ),
    )
    set_route, set_ids, filters = _set_entry_route(
        client,
        company_id,
        loaded[(ROUTE_ANALYTICS, "dimensionSetEntries")],
        analytics_sets,
        population_keys,
        shortcuts,
        departments,
        groups,
        dynamic_ids=_dynamic_ids(raw_dir),
    )
    routes = [expand, dynamic, shortcut_route, set_route]
    for route in routes:
        covered = route.with_department if route.per_entry else None
        print(
            f"Route {route.key}: works={route.works} rows={route.rows} "
            f"department={covered} in {fmt_seconds(route.seconds)}."
        )
    return routes, joined, set_ids, filters, shortcuts


def _expand_route(
    client: BusinessCentralClient,
    company_id: str,
    model: MetadataModel,
    population_keys: Sequence[str],
    departments: Sequence[str],
    groups: Sequence[str],
    raw_dir: Path,
) -> RouteAssessment:
    nav = _dimension_nav(model)
    shapes = (
        {
            "$top": str(SAMPLE_TOP),
            "$select": "entryNumber,postingDate,accountNumber,debitAmount,creditAmount",
            "$expand": f"{nav}($select=code,valueCode,valueDisplayName)",
        },
        {
            "$top": str(SAMPLE_TOP),
            "$select": "entryNumber,postingDate,accountNumber,debitAmount,creditAmount",
            "$expand": nav,
        },
        {"$top": str(SAMPLE_TOP), "$expand": nav},
    )
    sample_rows: list[dict[str, Any]] = []
    sample_status: int | None = None
    sample_seconds = 0.0
    sample_error = ""
    winning: dict[str, str] | None = None
    for query in shapes:
        started = time.perf_counter()
        previous = client.timeout
        client.timeout = 120.0
        try:
            result = client.fetch(
                ROUTE_V2,
                "generalLedgerEntries",
                company_id=company_id,
                query=query,
                parse_decimal=True,
            )
        finally:
            client.timeout = previous
        sample_seconds = time.perf_counter() - started
        sample_status = result.status_code
        sample_error = result.error
        rows = _value_rows(result.payload)
        if result.status_code == 200 and _expand_present(rows, nav):
            sample_rows = rows
            winning = query
            break
        sample_rows = rows
        if result.status_code == 200 and not _expand_present(rows, nav):
            continue
        if result.status_code not in {400, 404}:
            break
    _save_json(raw_dir / "expand_sample.json", {"value": sample_rows}, client)
    sample_lines = _flatten_lines(sample_rows, nav)
    works = sample_status == 200 and _expand_present(sample_rows, nav)
    if not works or sample_seconds > SAMPLE_LIMIT_SECONDS:
        reason = sample_error or "Stichprobe ohne Dimensionszeilen."
        if works and sample_seconds > SAMPLE_LIMIT_SECONDS:
            reason = (
                f"Stichprobe {fmt_seconds(sample_seconds)} für {len(sample_rows)} Posten. "
                "Der vollständige Lauf ist damit nicht vertretbar."
            )
        detail = (
            f"Navigation {nav}. Stichprobe $top={SAMPLE_TOP} in {fmt_seconds(sample_seconds)}, "
            f"HTTP {sample_status}, {len(sample_rows)} Posten, "
            f"{len(sample_lines)} Dimensionszeilen. "
            f"{reason}"
        )
        return _coverage_assessment(
            "expand",
            works=False if not works else True,
            complete=False,
            status=sample_status,
            seconds=sample_seconds,
            rows=len(sample_rows),
            population_keys=[norm_key(row.get("entryNumber")) for row in sample_rows],
            lines=sample_lines,
            departments=departments,
            groups=groups,
            detail=detail,
            per_entry=True,
        )

    full_rows, full_seconds, full_error = _expand_full(
        client,
        company_id,
        winning or shapes[-1],
        nav,
    )
    if full_rows is None:
        detail = (
            f"Navigation {nav}. Stichprobe $top={SAMPLE_TOP} in {fmt_seconds(sample_seconds)}, "
            f"{len(sample_rows)} Posten, {len(sample_lines)} Dimensionszeilen. "
            f"Vollständiger Lauf nicht verwendbar: {full_error}"
        )
        return _coverage_assessment(
            "expand",
            works=True,
            complete=False,
            status=sample_status,
            seconds=sample_seconds,
            rows=len(sample_rows),
            population_keys=[norm_key(row.get("entryNumber")) for row in sample_rows],
            lines=sample_lines,
            departments=departments,
            groups=groups,
            detail=detail,
            per_entry=True,
        )
    _save_json(raw_dir / "expand_full.json", {"value": _public_lines(full_rows, nav)}, client)
    full_lines = _flatten_lines(full_rows, nav)
    detail = (
        f"Navigation {nav}. Stichprobe $top={SAMPLE_TOP} in {fmt_seconds(sample_seconds)}. "
        f"Vollständiger Lauf in {fmt_seconds(full_seconds)}, {len(full_rows)} Posten, "
        f"{len(full_lines)} Dimensionszeilen."
    )
    covered_population = population_keys
    line_keys = {entry for entry, _code, _value in full_lines}
    # Coverage is against analytics entry numbers. Lines carry v2 entry numbers.
    return _coverage_assessment(
        "expand",
        works=True,
        complete=True,
        status=200,
        seconds=full_seconds,
        rows=len(full_rows),
        population_keys=covered_population,
        lines=full_lines,
        departments=departments,
        groups=groups,
        detail=detail + f" Posten mit mindestens einer Dimensionszeile: {len(line_keys)}.",
        per_entry=True,
        restrict_to_population=True,
    )


def _expand_full(
    client: BusinessCentralClient,
    company_id: str,
    winning: Mapping[str, str],
    nav: str,
) -> tuple[list[dict[str, Any]] | None, float, str]:
    query = {key: value for key, value in winning.items() if key != "$top"}
    if "$expand" not in query:
        query["$expand"] = nav
    started = time.perf_counter()
    previous = client.timeout
    client.timeout = FULL_TIMEOUT_SECONDS
    try:
        rows = client.get_collection(
            ROUTE_V2,
            "generalLedgerEntries",
            company_id=company_id,
            query=query,
            parse_decimal=True,
        )
    except BusinessCentralError as exc:
        return None, time.perf_counter() - started, str(exc)
    finally:
        client.timeout = previous
    return rows, time.perf_counter() - started, ""


def _dynamic_route(
    client: BusinessCentralClient,
    company_id: str,
    model: MetadataModel,
    analytics_sets: Sequence[tuple[str, str]],
    population_keys: Sequence[str],
    departments: Sequence[str],
    groups: Sequence[str],
    raw_dir: Path,
) -> RouteAssessment:
    names = []
    for candidate in ("dynamicDimensions", "dynamicDimension"):
        if candidate not in names:
            names.append(candidate)
    for name in model.entity_sets:
        if "dynamicdimension" in name.casefold() and name not in names:
            names.insert(0, name)
    last_status: int | None = None
    last_error = ""
    rows: list[dict[str, Any]] = []
    seconds = 0.0
    used = names[0]
    for name in names:
        started = time.perf_counter()
        try:
            rows = client.get_collection(
                ROUTE_ANALYTICS,
                name,
                company_id=company_id,
                parse_decimal=True,
            )
            seconds = time.perf_counter() - started
            used = name
            last_status = 200
            last_error = ""
            break
        except BusinessCentralError as exc:
            seconds = time.perf_counter() - started
            last_error = str(exc)
            last_status = exc.status_code
            rows = []
    _save_json(raw_dir / "dynamic_dimensions.json", {"value": rows}, client)
    lines = [
        (
            norm_key(row.get("dimensionSetID")),
            str(row.get("customDimensionCode") or "").strip(),
            str(row.get("customDimensionValueCode") or "").strip(),
        )
        for row in rows
    ]
    # Tag analytics entries, not dimension-set rows: rebuild lines as entry-level below.
    entry_lines = _tag_entries(analytics_sets, lines)
    codes = sorted({code for _set_id, code, _value in lines if code})
    distinct_sets = len({set_id for set_id, _code, _value in lines if set_id not in {"", "0"}})
    detail = (
        f"Entität {used}. Verschiedene Dimensionscodes: {', '.join(codes) if codes else 'keine'}. "
        f"Verschiedene dimensionSetID ungleich 0: {distinct_sets}."
    )
    if last_error and not rows:
        detail = f"{detail} {last_error}"
    works = last_status == 200 and len(rows) > 0
    return _coverage_assessment(
        "dynamic",
        works=works,
        complete=works,
        status=last_status,
        seconds=seconds,
        rows=len(rows),
        population_keys=population_keys,
        lines=entry_lines,
        departments=departments,
        groups=groups,
        detail=detail,
        per_entry=True,
        restrict_to_population=True,
    )


def _set_entry_route(
    client: BusinessCentralClient,
    company_id: str,
    cached_rows: Sequence[Mapping[str, Any]],
    analytics_sets: Sequence[tuple[str, str]],
    population_keys: Sequence[str],
    shortcuts: Sequence[ShortcutSlot],
    departments: Sequence[str],
    groups: Sequence[str],
    dynamic_ids: set[str],
) -> tuple[RouteAssessment, SetIdStats, list[FilterProbe]]:
    probes = [
        ("", {"$top": "1", "$count": "true"}),
        ("dimensionSetID gt 0", {"$top": "1", "$count": "true", "$filter": "dimensionSetID gt 0"}),
        ("valueCount gt 0", {"$top": "1", "$count": "true", "$filter": "valueCount gt 0"}),
    ]
    filters: list[FilterProbe] = []
    for expression, query in probes:
        result = client.fetch(
            ROUTE_ANALYTICS,
            "dimensionSetEntries",
            company_id=company_id,
            query=query,
        )
        filters.append(
            FilterProbe(
                expression=expression,
                status=result.status_code,
                count=_odata_count(result.payload),
                error=result.error,
            )
        )
    unfiltered = filters[0].count if filters else len(cached_rows)
    rows = list(cached_rows)
    if unfiltered and not rows:
        try:
            rows = client.get_collection(
                ROUTE_ANALYTICS,
                "dimensionSetEntries",
                company_id=company_id,
                parse_decimal=True,
            )
        except BusinessCentralError as exc:
            filters.append(FilterProbe("voller Abruf", exc.status_code, None, str(exc)))
    set_lines = _set_entry_lines(rows, shortcuts)
    entry_lines = _tag_entries(analytics_sets, set_lines)
    present_ids = {
        norm_key(row.get("dimensionSetID"))
        for row in rows
        if norm_key(row.get("dimensionSetID")) not in {"", "0"}
    }
    id_values = [set_id for _entry, set_id in analytics_sets]
    nonzero = [set_id for set_id in id_values if set_id not in {"", "0"}]
    distinct = set(nonzero)
    stats = SetIdStats(
        entries=len(id_values),
        zero=len(id_values) - len(nonzero),
        nonzero=len(nonzero),
        distinct_nonzero=len(distinct),
        matched_set_entries=len(distinct & present_ids),
        matched_dynamic=len(distinct & dynamic_ids),
    )
    status = filters[0].status if filters else (200 if rows else None)
    count = unfiltered if unfiltered is not None else len(rows)
    works = bool(count) or bool(rows)
    detail = (
        "Die Entität ist eine Zeile je dimensionSetID mit den Shortcut-Werten "
        "dimension1ValueCode bis dimension8ValueCode. Den Dimensionscode des Platzes "
        "liefert die Shortcut-Zeile, nicht diese Entität."
    )
    route = _coverage_assessment(
        "set_entries",
        works=works,
        complete=works,
        status=status,
        seconds=None,
        rows=count or len(rows),
        population_keys=population_keys,
        lines=entry_lines,
        departments=departments,
        groups=groups,
        detail=detail,
        per_entry=True,
        restrict_to_population=True,
    )
    return route, stats, filters


def _trial_balances(
    client: BusinessCentralClient,
    entity: Entity,
    company_id: str,
    as_of: date,
) -> tuple[list[tuple[date, list[dict[str, Any]], list[TrialRow]]], str]:
    collected: list[tuple[date, list[dict[str, Any]], list[TrialRow]]] = []
    for day in trial_dates(as_of):
        raw_rows, mapped, error = _one_trial(client, entity, company_id, day)
        if error:
            return collected, error
        collected.append((day, raw_rows, mapped))
        print(f"trialBalances {day.isoformat()}: {len(mapped)} rows")
    return collected, ""


def _one_trial(
    client: BusinessCentralClient,
    entity: Entity,
    company_id: str,
    day: date,
) -> tuple[list[dict[str, Any]], list[TrialRow], str]:
    iso = day.isoformat()
    last_error = ""
    for expression in (f"dateFilter eq {iso}", f"dateFilter eq {iso}T00:00:00Z"):
        try:
            rows = client.get_collection(
                ROUTE_V2,
                "trialBalances",
                select=entity.select,
                odata_filter=expression,
                company_id=company_id,
                parse_decimal=True,
            )
        except BusinessCentralError as exc:
            last_error = str(exc)
            continue
        print(f"trialBalances filter accepted, {len(rows)} rows.")
        return rows, [_map_trial(row) for row in rows], ""
    return [], [], last_error or "trialBalances did not respond."


def _map_trial(row: Mapping[str, Any]) -> TrialRow:
    return TrialRow(
        number=norm_key(row.get("number")),
        name=str(row.get("display") or "").strip(),
        account_type=readable_token(row.get("accountType")),
        total_debit=parse_amount(row.get("totalDebit")),
        total_credit=parse_amount(row.get("totalCredit")),
        balance_debit=parse_amount(row.get("balanceAtDateDebit")),
        balance_credit=parse_amount(row.get("balanceAtDateCredit")),
        echoed_filter=str(row.get("dateFilter") or "").strip(),
    )


def _coverage_assessment(
    key: str,
    *,
    works: bool,
    complete: bool,
    status: int | None,
    seconds: float | None,
    rows: int,
    population_keys: Sequence[str],
    lines: Sequence[tuple[str, str, str]],
    departments: Sequence[str],
    groups: Sequence[str],
    detail: str,
    per_entry: bool,
    restrict_to_population: bool = False,
) -> RouteAssessment:
    population = list(population_keys)
    department_keys = _keys_for(lines, departments)
    group_keys = _keys_for(lines, groups)
    if restrict_to_population:
        population_set = set(population)
        department_keys = [item for item in department_keys if item in population_set]
        group_keys = [item for item in group_keys if item in population_set]
    return RouteAssessment(
        key=key,
        works=works,
        per_entry=per_entry,
        complete=complete and works,
        http_status=status,
        seconds=seconds,
        rows=rows,
        population=len(population),
        with_department=count_covered(population, department_keys) if per_entry else None,
        with_customer_group=count_covered(population, group_keys) if per_entry else None,
        detail=detail,
    )


def _keys_for(lines: Sequence[tuple[str, str, str]], codes: Sequence[str]) -> list[str]:
    wanted = {code.casefold() for code in codes}
    if not wanted:
        return []
    return [
        entry
        for entry, code, value in lines
        if code.casefold() in wanted and value.strip()
    ]


def _tag_entries(
    analytics_sets: Sequence[tuple[str, str]],
    set_lines: Sequence[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    by_set: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for set_id, code, value in set_lines:
        if set_id not in {"", "0"}:
            by_set[set_id].append((code, value))
    tagged: list[tuple[str, str, str]] = []
    for entry, set_id in analytics_sets:
        for code, value in by_set.get(set_id, []):
            tagged.append((entry, code, value))
    return tagged


def _set_entry_lines(
    rows: Sequence[Mapping[str, Any]],
    shortcuts: Sequence[ShortcutSlot],
) -> list[tuple[str, str, str]]:
    slot_code = {slot.index: slot.code for slot in shortcuts}
    lines: list[tuple[str, str, str]] = []
    for row in rows:
        set_id = norm_key(row.get("dimensionSetID"))
        for index in range(1, 9):
            value = str(row.get(f"dimension{index}ValueCode") or "").strip()
            code = slot_code.get(index, "")
            if code or value:
                lines.append((set_id, code, value))
    return lines


def _shortcuts(rows: Sequence[Mapping[str, Any]]) -> list[ShortcutSlot]:
    if not rows:
        return []
    row = rows[0]
    slots: list[ShortcutSlot] = []
    for index in range(1, 9):
        code = str(row.get(f"dim{index}Code") or "").strip()
        name = str(row.get(f"dim{index}Name") or "").strip()
        caption = str(row.get(f"dim{index}Caption") or "").strip()
        if code or name or caption:
            slots.append(ShortcutSlot(index, code, name, caption))
    return slots


def _flatten_lines(rows: Sequence[Mapping[str, Any]], nav: str) -> list[tuple[str, str, str]]:
    lines: list[tuple[str, str, str]] = []
    for row in rows:
        entry = norm_key(row.get("entryNumber"))
        nested = row.get(nav)
        if isinstance(nested, dict):
            nested = nested.get("value")
        if not isinstance(nested, list):
            continue
        for item in nested:
            if not isinstance(item, dict):
                continue
            lines.append(
                (
                    entry,
                    str(item.get("code") or "").strip(),
                    str(item.get("valueCode") or "").strip(),
                )
            )
    return lines


def _public_lines(rows: Sequence[Mapping[str, Any]], nav: str) -> list[dict[str, Any]]:
    """Drop technical ids before the gitignored raw file is written."""
    public: list[dict[str, Any]] = []
    for row in rows:
        nested = row.get(nav)
        if isinstance(nested, dict):
            nested = nested.get("value")
        values = []
        if isinstance(nested, list):
            for item in nested:
                if not isinstance(item, dict):
                    continue
                values.append(
                    {
                        "code": item.get("code"),
                        "valueCode": item.get("valueCode"),
                        "valueDisplayName": item.get("valueDisplayName"),
                    }
                )
        public.append(
            {
                "entryNumber": norm_key(row.get("entryNumber")),
                "accountNumber": row.get("accountNumber"),
                nav: values,
            }
        )
    return public


def _dynamic_ids(raw_dir: Path) -> set[str]:
    path = raw_dir / "dynamic_dimensions.json"
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    rows = payload.get("value") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return set()
    return {
        norm_key(row.get("dimensionSetID"))
        for row in rows
        if isinstance(row, dict) and norm_key(row.get("dimensionSetID")) not in {"", "0"}
    }


def _customer_details(rows: Sequence[Mapping[str, Any]]) -> list[DetailRow]:
    return [
        DetailRow(
            parent=norm_key(row.get("cleEntryNo")),
            party=norm_key(row.get("dcleCustomerNo")),
            posting_date=parse_iso_date(row.get("dclePostingDate")),
            amount=parse_amount(row.get("dcleAmountLCY")),
        )
        for row in rows
    ]


def _vendor_details(rows: Sequence[Mapping[str, Any]]) -> list[DetailRow]:
    return [
        DetailRow(
            parent=norm_key(row.get("vleEntryNo")),
            party=norm_key(row.get("dvleVendorNo")),
            posting_date=parse_iso_date(row.get("dvlePostingDate")),
            amount=parse_amount(row.get("dvleAmountLCY")),
        )
        for row in rows
    ]


def _count(client: BusinessCentralClient, route: str, name: str, company_id: str) -> int:
    result = client.fetch(route, name, company_id=company_id, query={"$top": "1", "$count": "true"})
    if result.status_code != 200:
        raise BusinessCentralError(result.error or f"{name} returned HTTP {result.status_code}.")
    counted = _odata_count(result.payload)
    if counted is None:
        rows = _value_rows(result.payload)
        return len(rows)
    return counted


def _entity(catalog: Mapping[str, tuple[Entity, ...]], route: str, name: str) -> Entity:
    for entity in catalog[route]:
        if entity.entity_set == name:
            return entity
    raise BusinessCentralError(f"Catalog is missing {name}.")


def _require(rows: Sequence[Mapping[str, Any]], *fields: str) -> None:
    if not rows:
        return
    missing = [field for field in fields if field not in rows[0]]
    if missing:
        joined = ", ".join(missing)
        raise BusinessCentralError(f"Response is missing fields: {joined}.")


def _dimension_nav(model: MetadataModel) -> str:
    info = model.entities.get("generalLedgerEntries")
    if info is None:
        return "dimensionSetLines"
    for nav in info.navigation:
        if "dimension" in nav.name.casefold():
            return nav.name
    return "dimensionSetLines"


def _dimension_entity_sets(models: Mapping[str, MetadataModel]) -> tuple[str, ...]:
    names: list[str] = []
    for model in models.values():
        for name in model.entity_sets:
            if "dimension" in name.casefold() and name not in names:
                names.append(name)
    return tuple(names)


def _expand_present(rows: Sequence[Mapping[str, Any]], nav: str) -> bool:
    return any(nav in row for row in rows)


def _value_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    value = payload.get("value")
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _odata_count(payload: Any) -> int | None:
    if not isinstance(payload, dict) or "@odata.count" not in payload:
        return None
    raw = payload["@odata.count"]
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        return raw
    text = str(raw).strip()
    if text.isdigit():
        return int(text)
    return None


def _save_json(path: Path, payload: Any, client: BusinessCentralClient) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, default=str)
    path.write_text(client.redact(text), encoding="utf-8")


def _needles(client: BusinessCentralClient, company_id: str) -> tuple[str, ...]:
    values = (client.tenant_id, client.client_id, client._client_secret, company_id)
    return tuple(value for value in values if value)


def _is_department(blob: str) -> bool:
    text = blob.casefold()
    return "abteilung" in text or "department" in text


def _is_group(blob: str) -> bool:
    text = blob.casefold()
    return any(token in text for token in ("debitorengruppe", "kundengruppe", "customer group"))
