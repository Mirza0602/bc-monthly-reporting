"""AP-01 calculations and German reports. HTTP stays in datenbestand_run."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

CATEGORY_LABELS = {
    "income": "Einnahmen",
    "cost of goods sold": "Wareneinsatz",
    "expense": "Ausgaben",
    "assets": "Anlagen",
    "liabilities": "Verbindlichkeiten",
    "equity": "Eigenkapital",
}
_ODATA_ESCAPES = (
    ("_x0020_", " "),
    ("_x002E_", "."),
    ("_x002F_", "/"),
    ("_x002B_", "+"),
    ("_x0028_", "("),
    ("_x0029_", ")"),
    ("_x002D_", "-"),
)
CENT = Decimal("0.01")
WATCH_ACCOUNTS = ("0210", "0280", "1085", "2720", "4091")
MONTHS = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)
INCOME_NAMES = frozenset(
    {
        "einnahmen",
        "income",
        "ertraege",
        "erträge",
        "erlöse",
        "erloese",
        "umsatzerlöse",
        "umsatzerloese",
        "revenue",
    }
)
COGS_NAMES = frozenset({"wareneinsatz", "cost of goods sold", "cogs"})
POSTING_TYPES = frozenset({"posting", "posting account", "buchung"})
ROUTE_ORDER = ("expand", "dynamic", "shortcut", "set_entries")
ROUTE_TITLE = {
    "expand": "v2.0 generalLedgerEntries mit $expand=dimensionSetLines",
    "dynamic": "Analytics dynamicDimensions",
    "shortcut": "Analytics dimensions",
    "set_entries": "Analytics dimensionSetEntries",
}
JOIN_TEXT = {
    "expand": "entryNumber der v2.0-Sachposten auf entryNo der Analytics-Sachposten",
    "dynamic": "dimensionSetID",
    "shortcut": "kein Postenbezug",
    "set_entries": "dimensionSetID",
}


@dataclass(frozen=True)
class FieldInfo:
    name: str
    type_name: str
    nullable: str
    key: bool


@dataclass(frozen=True)
class NavInfo:
    name: str
    type_name: str


@dataclass(frozen=True)
class EntityInfo:
    entity_set: str
    type_name: str
    keys: tuple[str, ...]
    fields: tuple[FieldInfo, ...]
    navigation: tuple[NavInfo, ...]


@dataclass(frozen=True)
class MetadataModel:
    entities: dict[str, EntityInfo]
    enums: dict[str, tuple[str, ...]]
    entity_sets: tuple[str, ...]


@dataclass(frozen=True)
class GlRow:
    posting_date: date | None
    amount: Decimal
    account: str
    ledger: str
    entry_no: str


@dataclass(frozen=True)
class AccountInfo:
    number: str
    name: str
    category: str
    subcategory: str
    analytics_category: str


@dataclass(frozen=True)
class PeriodTotal:
    year: int
    month: int | None
    count: int
    debit: Decimal
    credit: Decimal

    @property
    def balance(self) -> Decimal:
        return self.debit - self.credit


@dataclass(frozen=True)
class CategoryTotal:
    category: str
    subcategory: str
    year: int | None
    count: int
    balance_bc: Decimal
    debit: Decimal
    credit: Decimal

    @property
    def balance_guv(self) -> Decimal:
        return -self.balance_bc


@dataclass(frozen=True)
class AccountSum:
    number: str
    name: str
    category: str
    subcategory: str
    analytics_category: str
    total: Decimal


@dataclass(frozen=True)
class DetailRow:
    parent: str
    party: str
    posting_date: date | None
    amount: Decimal


@dataclass(frozen=True)
class OpenTotal:
    entries: int
    parties: int
    amount: Decimal


@dataclass(frozen=True)
class SignCheck:
    matched: int
    equal: int
    analytics_rows: int
    v2_rows: int


@dataclass(frozen=True)
class TrialRow:
    number: str
    name: str
    account_type: str
    total_debit: Decimal
    total_credit: Decimal
    balance_debit: Decimal
    balance_credit: Decimal
    echoed_filter: str


@dataclass(frozen=True)
class DiffRow:
    number: str
    name: str
    account_type: str
    snapshot_net: Decimal
    net_change: Decimal
    balance_at: Decimal
    day_net: Decimal

    @property
    def diff_change(self) -> Decimal:
        return self.net_change - self.snapshot_net

    @property
    def diff_balance(self) -> Decimal:
        return self.balance_at - self.snapshot_net


@dataclass(frozen=True)
class TrialComparison:
    as_of: date
    row_count: int
    signature: tuple[str, str, str, str]
    echoed: tuple[str, ...]
    posting_diffs: tuple[DiffRow, ...]
    other_diffs: tuple[DiffRow, ...]
    posting_compared: int
    change_zero: int
    balance_zero: int
    day_zero: int
    snapshot_sum: Decimal
    trial_change_sum: Decimal
    trial_balance_sum: Decimal


@dataclass(frozen=True)
class DimensionMaster:
    code: str
    name: str
    value_count: int
    values: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ShortcutSlot:
    index: int
    code: str
    name: str
    caption: str


@dataclass(frozen=True)
class FilterProbe:
    expression: str
    status: int | None
    count: int | None
    error: str


@dataclass(frozen=True)
class JoinStats:
    analytics_entries: int
    v2_entries: int
    intersection: int
    analytics_only: int
    v2_only: int
    duplicate_analytics: int
    duplicate_v2: int


@dataclass(frozen=True)
class SetIdStats:
    entries: int
    zero: int
    nonzero: int
    distinct_nonzero: int
    matched_set_entries: int
    matched_dynamic: int


@dataclass(frozen=True)
class RouteAssessment:
    key: str
    works: bool
    per_entry: bool
    complete: bool
    http_status: int | None
    seconds: float | None
    rows: int
    population: int
    with_department: int | None
    with_customer_group: int | None
    detail: str


@dataclass(frozen=True)
class Profile:
    stand: date
    as_of: date
    run_day: date
    gl_count: int
    undated: int
    oldest: date | None
    newest: date | None
    after_cutoff: int
    after_oldest: date | None
    after_newest: date | None
    years: tuple[PeriodTotal, ...]
    months: tuple[PeriodTotal, ...]
    sign: SignCheck | None
    category_source: str
    categories: tuple[CategoryTotal, ...]
    subcategories: tuple[CategoryTotal, ...]
    uncategorized: tuple[AccountSum, ...]
    watch: tuple[AccountSum, ...]
    customers: OpenTotal
    vendors: OpenTotal
    routes: tuple[RouteAssessment, ...]
    masters: tuple[DimensionMaster, ...]
    department_codes: tuple[str, ...]
    customer_group_codes: tuple[str, ...]
    department_values: tuple[str, ...]
    customer_group_values: tuple[str, ...]
    join: JoinStats | None
    set_ids: SetIdStats
    filter_probes: tuple[FilterProbe, ...]
    shortcuts: tuple[ShortcutSlot, ...]
    trials: tuple[TrialComparison, ...]
    trial_error: str
    trial_same_signature: bool
    budget_rows: int
    budget_entry_rows: int
    closing_rows: int
    recommendation_key: str
    recommendation: str
    report_month: tuple[int, int] | None
    prior_year: bool
    dimension_entity_sets: tuple[str, ...]
    findings_ok: tuple[str, ...]
    findings_diff: tuple[str, ...]


def readable_token(value: Any) -> str:
    """Turn OData enum identifiers such as Cost_x0020_of_x0020_Goods into words."""
    text = str(value or "")
    for encoded, plain in _ODATA_ESCAPES:
        text = text.replace(encoded, plain)
    return text.strip()


def category_label(value: Any) -> str:
    """Map the six Business Central account categories to the German chart names."""
    text = readable_token(value)
    return CATEGORY_LABELS.get(text.casefold(), text)


def without_long_dashes(text: str) -> str:
    return (
        text.replace(" \u2013 ", " / ")
        .replace(" \u2014 ", " / ")
        .replace("\u2013", " / ")
        .replace("\u2014", " / ")
    )


def parse_amount(value: Any) -> Decimal:
    """Parse a Business Central amount in English or German format."""
    if value is None or value == "":
        return Decimal(0)
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError("Amount is a boolean.")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        return Decimal(0)
    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]
    if text.endswith("-"):
        negative = True
        text = text[:-1]
    if text.startswith("+"):
        text = text[1:]
    if text.startswith("-"):
        negative = True
        text = text[1:]
    for token in ("EUR", "€"):
        text = text.replace(token, "")
    if not text:
        return Decimal(0)
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        left, right = text.split(",", 1)
        if right.isdigit() and len(right) == 3 and left.replace(".", "").isdigit():
            text = left.replace(".", "") + right
        else:
            text = left.replace(".", "") + "." + right
    elif text.count(".") > 1:
        text = text.replace(".", "")
    number = Decimal(text)
    return -number if negative else number


def parse_iso_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def default_as_of(today: date) -> date:
    """Last day of the month before today."""
    return today.replace(day=1) - timedelta(days=1)


def parse_stichtag(value: str | None, today: date | None = None) -> date:
    current = today or date.today()
    if value is None or not value.strip():
        return default_as_of(current)
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def trial_dates(as_of: date) -> tuple[date, ...]:
    ordered: list[date] = []
    for item in (date(2025, 12, 31), date(2026, 6, 30), as_of):
        if item not in ordered:
            ordered.append(item)
    return tuple(ordered)


def cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def norm_key(value: Any) -> str:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return str(int(value))
        return format(value, "f")
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return norm_key(Decimal(str(value)))
    return str(value).strip()


def loose_number(value: str) -> str:
    text = value.strip()
    stripped = text.lstrip("0")
    return stripped or "0"


def fmt_money(value: Decimal) -> str:
    quantized = cents(value)
    sign = "-" if quantized < 0 else ""
    whole, frac = f"{abs(quantized):.2f}".split(".")
    groups: list[str] = []
    while whole:
        groups.append(whole[-3:])
        whole = whole[:-3]
    return f"{sign}{'.'.join(reversed(groups))},{frac}"


def fmt_int(value: int) -> str:
    sign = "-" if value < 0 else ""
    digits = str(abs(value))
    groups: list[str] = []
    while digits:
        groups.append(digits[-3:])
        digits = digits[:-3]
    return sign + ".".join(reversed(groups))


def fmt_date(value: date | None) -> str:
    if value is None:
        return "kein Datum"
    return value.strftime("%d.%m.%Y")


def fmt_seconds(value: float | None) -> str:
    if value is None:
        return "nicht gemessen"
    return f"{value:.1f}".replace(".", ",") + " s"


def fmt_share(part: int | None, whole: int) -> str:
    if part is None:
        return "nicht berechnet"
    if whole == 0:
        return "keine Bezugsmenge"
    pct = (Decimal(part) * Decimal(100) / Decimal(whole)).quantize(
        Decimal("0.1"),
        rounding=ROUND_HALF_UP,
    )
    return f"{pct:.1f}".replace(".", ",") + f" % ({fmt_int(part)} von {fmt_int(whole)})"


def fmt_month(year: int, month: int) -> str:
    return f"{MONTHS[month - 1]} {year}"


def cell(value: Any) -> str:
    return str(value).replace("|", "/").replace("\n", " ").strip()


def md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    head = "| " + " | ".join(cell(item) for item in headers) + " |"
    rule = "| " + " | ".join("---" for _ in headers) + " |"
    body = [
        "| " + " | ".join(cell(item) for item in row) + " |"
        for row in rows
    ]
    return "\n".join([head, rule, *body])


def assert_no_secrets(text: str, needles: Sequence[str]) -> None:
    """Refuse to write text that still contains credentials or directory ids."""
    if "Bearer " in text or "bearer " in text:
        raise RuntimeError("Output contains a bearer token.")
    for needle in needles:
        if needle and needle in text:
            raise RuntimeError("Output contains a forbidden identifier.")
    if "\u2013" in text or "\u2014" in text:
        raise RuntimeError("Output contains a dash character that the docs do not use.")


def parse_metadata(text: str) -> MetadataModel:
    """Read entity sets, fields, keys, and enums from an OData CSDL document."""
    cleaned = text.lstrip("\ufeff").strip()
    if cleaned.startswith("<?xml"):
        cleaned = cleaned.split("?>", 1)[1].lstrip()
    if not cleaned.startswith("<"):
        raise ValueError("Metadata is not XML.")
    root = ET.fromstring(cleaned)
    enums: dict[str, tuple[str, ...]] = {}
    types: dict[str, dict[str, Any]] = {}
    entity_sets: list[tuple[str, str]] = []
    for element in root.iter():
        local = _local(element.tag)
        if local == "EnumType":
            type_name = element.attrib.get("Name", "")
            members = tuple(
                child.attrib.get("Name", "")
                for child in list(element)
                if _local(child.tag) == "Member" and child.attrib.get("Name")
            )
            enums[type_name] = members
            enums[_qualified(element, type_name)] = members
        elif local == "EntityType":
            type_name = element.attrib.get("Name", "")
            types[type_name] = _parse_entity_type(element)
            types[_qualified(element, type_name)] = types[type_name]
        elif local == "EntitySet":
            entity_sets.append(
                (element.attrib.get("Name", ""), element.attrib.get("EntityType", ""))
            )
    entities: dict[str, EntityInfo] = {}
    for set_name, type_ref in entity_sets:
        if not set_name or set_name in entities:
            continue
        parsed = _resolve_type(type_ref, types)
        if parsed is None:
            continue
        keys = tuple(parsed["keys"])
        key_set = set(keys)
        fields = tuple(
            FieldInfo(
                name=name,
                type_name=_decorate_type(type_name, extra),
                nullable=nullable,
                key=name in key_set,
            )
            for name, type_name, nullable, extra in parsed["fields"]
        )
        navigation = tuple(
            NavInfo(name=name, type_name=_short_type(type_name))
            for name, type_name in parsed["navigation"]
        )
        short = type_ref.rsplit(".", 1)[-1] or type_ref
        entities[set_name] = EntityInfo(set_name, short, keys, fields, navigation)
    return MetadataModel(
        entities=entities,
        enums=enums,
        entity_sets=tuple(name for name, _type_ref in entity_sets if name),
    )


def render_feldinventar(
    catalog: Sequence[tuple[str, str, str | None]],
    models: Mapping[str, MetadataModel],
    stand: date,
) -> str:
    """German field inventory. Structures only, no data values."""
    lines = [
        "# Feldinventar",
        "",
        f"Stand: {fmt_date(stand)}. Quelle ist das OData-$metadata der API v2.0 "
        "und der Analytics API microsoft/analytics/v1.0.",
        "",
        "Enthalten sind die 31 Entitäten aus dem Katalog. Das Dokument nennt Felder, "
        "Typen und Schlüssel. Datenwerte stehen hier nicht.",
        "",
        "Nullable ja gilt, wenn das Attribut im Schema fehlt. Das ist der OData-Standard. "
        "Der Schlüssel kommt aus dem Key der EntityType. "
        "Leerzeichen in Enum-Namen schreibt das Schema als _x0020_. "
        "In der Tabelle stehen sie als Leerzeichen. Ein leeres Mitglied steht als (leer).",
        "",
    ]
    grouped: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
    for route, entity_set, catalog_key in catalog:
        grouped[route].append((entity_set, catalog_key))
    for route, title in (
        ("v2.0", "API v2.0"),
        ("microsoft/analytics/v1.0", "Analytics API"),
    ):
        lines.extend([f"## {title}", ""])
        model = models.get(route)
        for entity_set, catalog_key in grouped.get(route, []):
            lines.extend(_render_entity(entity_set, catalog_key, model))
    lines.extend(["## Enumerationen aus dem Schema", ""])
    used: dict[str, tuple[str, ...]] = {}
    for route, entity_set, _catalog_key in catalog:
        model = models.get(route)
        if model is None:
            continue
        info = model.entities.get(entity_set)
        if info is None:
            continue
        for field in info.fields:
            members = _enum_members(field.type_name, model)
            if not members:
                continue
            labels = tuple(readable_token(member) or "(leer)" for member in members)
            used[field.type_name.split(",")[0].strip()] = labels
    if not used:
        lines.append("Keine Enumerationen an den gelesenen Feldern.")
        lines.append("")
    else:
        lines.append(
            md_table(
                ("Typ", "Mitglieder"),
                [(name, ", ".join(members)) for name, members in sorted(used.items())],
            )
        )
        lines.append("")
    text = without_long_dashes("\n".join(lines).rstrip() + "\n")
    assert_no_secrets(text, ())
    return text


def split_amount(amount: Decimal) -> tuple[Decimal, Decimal]:
    if amount > 0:
        return amount, Decimal(0)
    if amount < 0:
        return Decimal(0), -amount
    return Decimal(0), Decimal(0)


def period_totals(rows: Sequence[GlRow], *, monthly: bool) -> list[PeriodTotal]:
    debit: dict[tuple[int, int | None], Decimal] = defaultdict(lambda: Decimal(0))
    credit: dict[tuple[int, int | None], Decimal] = defaultdict(lambda: Decimal(0))
    counts: dict[tuple[int, int | None], int] = defaultdict(int)
    for row in rows:
        if row.posting_date is None:
            continue
        key = (row.posting_date.year, row.posting_date.month if monthly else None)
        left, right = split_amount(row.amount)
        debit[key] += left
        credit[key] += right
        counts[key] += 1
    totals = [
        PeriodTotal(year, month, counts[(year, month)], debit[(year, month)], credit[(year, month)])
        for year, month in sorted(counts)
    ]
    return totals


def category_totals(
    rows: Sequence[GlRow],
    accounts: Mapping[str, AccountInfo],
) -> list[CategoryTotal]:
    grouped: dict[tuple[str, int], list[Decimal]] = defaultdict(list)
    for row in rows:
        if row.ledger != "guv" or row.posting_date is None:
            continue
        info = accounts.get(row.account)
        category = info.category.strip() if info and info.category.strip() else "ohne Kategorie"
        grouped[(category, row.posting_date.year)].append(row.amount)
    totals: list[CategoryTotal] = []
    for category, year in sorted(grouped, key=lambda item: (_category_rank(item[0]), item[1])):
        amounts = grouped[(category, year)]
        balance = sum(amounts, Decimal(0))
        left = sum((amount for amount in amounts if amount > 0), Decimal(0))
        right = sum((-amount for amount in amounts if amount < 0), Decimal(0))
        totals.append(CategoryTotal(category, "", year, len(amounts), balance, left, right))
    return totals


def subcategory_totals(
    rows: Sequence[GlRow],
    accounts: Mapping[str, AccountInfo],
) -> list[CategoryTotal]:
    grouped: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
    for row in rows:
        if row.ledger != "guv":
            continue
        info = accounts.get(row.account)
        category = info.category.strip() if info and info.category.strip() else "ohne Kategorie"
        if _category_kind(category) not in {"income", "cogs"}:
            continue
        raw_subcategory = info.subcategory.strip() if info else ""
        subcategory = raw_subcategory or "ohne Unterkategorie"
        grouped[(category, subcategory)].append(row.amount)
    totals: list[CategoryTotal] = []
    order = sorted(grouped, key=lambda item: (_category_rank(item[0]), item[1]))
    for category, subcategory in order:
        amounts = grouped[(category, subcategory)]
        balance = sum(amounts, Decimal(0))
        left = sum((amount for amount in amounts if amount > 0), Decimal(0))
        right = sum((-amount for amount in amounts if amount < 0), Decimal(0))
        totals.append(
            CategoryTotal(category, subcategory, None, len(amounts), balance, left, right)
        )
    return totals


def account_totals(rows: Sequence[GlRow]) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    for row in rows:
        if row.account:
            totals[row.account] += row.amount
    return dict(totals)


def accounts_without_category(
    accounts: Sequence[AccountInfo],
    totals: Mapping[str, Decimal],
) -> list[AccountSum]:
    known = {account.number for account in accounts}
    rows: list[AccountSum] = []
    for account in accounts:
        if account.category.strip():
            continue
        rows.append(
            AccountSum(
                account.number,
                account.name,
                account.category,
                account.subcategory,
                account.analytics_category,
                totals.get(account.number, Decimal(0)),
            )
        )
    for number, total in totals.items():
        if number not in known:
            rows.append(AccountSum(number, "", "", "", "", total))
    return sorted(rows, key=lambda item: (loose_number(item.number), item.number))


def watch_accounts(
    accounts: Sequence[AccountInfo],
    totals: Mapping[str, Decimal],
) -> list[AccountSum]:
    by_exact = {account.number: account for account in accounts}
    by_loose: dict[str, list[AccountInfo]] = defaultdict(list)
    for account in accounts:
        by_loose[loose_number(account.number)].append(account)
    found: list[AccountSum] = []
    for number in WATCH_ACCOUNTS:
        account = by_exact.get(number)
        if account is None and len(by_loose.get(loose_number(number), [])) == 1:
            account = by_loose[loose_number(number)][0]
        if account is None:
            found.append(AccountSum(number, "", "", "", "", totals.get(number, Decimal(0))))
            continue
        found.append(
            AccountSum(
                account.number,
                account.name,
                account.category,
                account.subcategory,
                account.analytics_category,
                totals.get(account.number, Decimal(0)),
            )
        )
    return found


def open_at(rows: Sequence[DetailRow], as_of: date) -> OpenTotal:
    """Remaining amount is the sum of detail lines posted on or before the cutoff."""
    sums: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    parties: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        if not row.parent or row.posting_date is None or row.posting_date > as_of:
            continue
        sums[row.parent] += row.amount
        if row.party:
            parties[row.parent].add(row.party)
    open_rows = {key: cents(value) for key, value in sums.items() if cents(value) != 0}
    names: set[str] = set()
    for key in open_rows:
        names.update(parties[key])
    amount = sum(open_rows.values(), Decimal(0))
    return OpenTotal(len(open_rows), len(names), amount)


def sign_check(
    analytics: Sequence[tuple[str, Decimal]],
    v2_rows: Sequence[tuple[str, Decimal, Decimal]],
) -> SignCheck:
    expected: dict[str, Decimal] = {}
    for key, debit, credit in v2_rows:
        expected[key] = debit - credit
    matched = 0
    equal = 0
    seen: set[str] = set()
    for key, amount in analytics:
        if key in seen or key not in expected:
            continue
        seen.add(key)
        matched += 1
        if cents(amount) == cents(expected[key]):
            equal += 1
    return SignCheck(matched, equal, len(analytics), len(v2_rows))


def is_department(code: str, name: str) -> bool:
    blob = f"{code} {name}".casefold()
    return "abteilung" in blob or code.casefold() in {"department", "dept"}


def is_customer_group(code: str, name: str) -> bool:
    blob = f"{code} {name}".casefold()
    return any(
        token in blob
        for token in ("debitorengruppe", "kundengruppe", "customer group", "cust. group")
    )


def classify_dimensions(
    masters: Sequence[DimensionMaster],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    departments = tuple(item.code for item in masters if is_department(item.code, item.name))
    groups = tuple(item.code for item in masters if is_customer_group(item.code, item.name))
    return departments, groups


def count_covered(
    entry_keys: Sequence[str],
    tagged_keys: Sequence[str],
) -> int:
    population = set(entry_keys)
    return len(population & set(tagged_keys))


def join_stats(analytics_keys: Sequence[str], v2_keys: Sequence[str]) -> JoinStats:
    analytics = set(analytics_keys)
    v2 = set(v2_keys)
    return JoinStats(
        analytics_entries=len(analytics_keys),
        v2_entries=len(v2_keys),
        intersection=len(analytics & v2),
        analytics_only=len(analytics - v2),
        v2_only=len(v2 - analytics),
        duplicate_analytics=len(analytics_keys) - len(analytics),
        duplicate_v2=len(v2_keys) - len(v2),
    )


def is_posting_type(account_type: str) -> bool:
    return account_type.casefold().strip() in POSTING_TYPES


def compare_trial(
    entries: Sequence[GlRow],
    trial: Sequence[TrialRow],
    accounts: Mapping[str, AccountInfo],
    as_of: date,
) -> TrialComparison:
    cumulative: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    day_net: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
    for row in entries:
        if not row.account or row.posting_date is None or row.posting_date > as_of:
            continue
        cumulative[row.account] += row.amount
        if row.posting_date == as_of:
            day_net[row.account] += row.amount
    exact, unique_loose = _number_index([*accounts.keys(), *cumulative.keys()])
    posting_diffs: list[DiffRow] = []
    other_diffs: list[DiffRow] = []
    posting_compared = 0
    change_zero = 0
    balance_zero = 0
    day_zero = 0
    snapshot_sum = Decimal(0)
    trial_change_sum = Decimal(0)
    trial_balance_sum = Decimal(0)
    seen: set[str] = set()
    for row in trial:
        number = _resolve_number(row.number, exact, unique_loose)
        if number in seen:
            continue
        seen.add(number)
        info = accounts.get(number)
        name = info.name if info and info.name else row.name
        account_type = info_type(info, row.account_type)
        snapshot_net = cumulative.get(number, Decimal(0))
        change = row.total_debit - row.total_credit
        balance = row.balance_debit - row.balance_credit
        day = day_net.get(number, Decimal(0))
        has_entries = number in cumulative
        posting = has_entries or is_posting_type(account_type)
        diff = DiffRow(
            number,
            name,
            account_type or row.account_type,
            snapshot_net,
            change,
            balance,
            day,
        )
        if not posting:
            if cents(change) != 0 or cents(balance) != 0:
                other_diffs.append(diff)
            continue
        posting_compared += 1
        snapshot_sum += snapshot_net
        trial_change_sum += change
        trial_balance_sum += balance
        if cents(diff.diff_change) == 0:
            change_zero += 1
        if cents(diff.diff_balance) == 0:
            balance_zero += 1
        if cents(change - day) == 0:
            day_zero += 1
        if cents(diff.diff_change) != 0 or cents(diff.diff_balance) != 0:
            posting_diffs.append(diff)
    for number, snapshot_net in cumulative.items():
        if number in seen:
            continue
        info = accounts.get(number)
        diff = DiffRow(
            number,
            info.name if info else "",
            "Posten ohne Saldenliste",
            snapshot_net,
            Decimal(0),
            Decimal(0),
            day_net.get(number, Decimal(0)),
        )
        posting_compared += 1
        snapshot_sum += snapshot_net
        if cents(snapshot_net) == 0:
            change_zero += 1
            balance_zero += 1
        else:
            posting_diffs.append(diff)
    posting_diffs.sort(key=_diff_sort)
    other_diffs.sort(key=_diff_sort)
    echoed = tuple(sorted({row.echoed_filter for row in trial if row.echoed_filter}))
    signature = (
        fmt_money(sum((row.total_debit for row in trial), Decimal(0))),
        fmt_money(sum((row.total_credit for row in trial), Decimal(0))),
        fmt_money(sum((row.balance_debit for row in trial), Decimal(0))),
        fmt_money(sum((row.balance_credit for row in trial), Decimal(0))),
    )
    return TrialComparison(
        as_of=as_of,
        row_count=len(trial),
        signature=signature,
        echoed=echoed,
        posting_diffs=tuple(posting_diffs),
        other_diffs=tuple(other_diffs),
        posting_compared=posting_compared,
        change_zero=change_zero,
        balance_zero=balance_zero,
        day_zero=day_zero,
        snapshot_sum=snapshot_sum,
        trial_change_sum=trial_change_sum,
        trial_balance_sum=trial_balance_sum,
    )


def info_type(info: AccountInfo | None, fallback: str) -> str:
    if info is None:
        return fallback
    return fallback or ""


def recommend(routes: Sequence[RouteAssessment]) -> tuple[str, str]:
    """Pick one per-entry route. Higher coverage wins. dynamicDimensions wins a tie."""
    candidates = [route for route in routes if route.per_entry and route.works and route.complete]
    if not candidates:
        return (
            "",
            "Keine geprüfte Route liefert Abteilung und Debitorengruppe für den ganzen "
            "Bestand der Sachposten. Ich baue deshalb noch nichts.",
        )

    def score(route: RouteAssessment) -> tuple[int, int]:
        covered = (route.with_department or 0) + (route.with_customer_group or 0)
        preference = {"dynamic": 3, "expand": 2, "set_entries": 1}.get(route.key, 0)
        return covered, preference

    chosen = max(candidates, key=score)
    name = ROUTE_TITLE[chosen.key]
    department = fmt_share(chosen.with_department, chosen.population)
    group = fmt_share(chosen.with_customer_group, chosen.population)
    paragraph = (
        f"Empfehlung: {name}. Der Abruf ist vollständig und dauerte {fmt_seconds(chosen.seconds)}. "
        f"Die Zuordnung läuft über {JOIN_TEXT[chosen.key]}. "
        f"Abteilung ist bei {department} der Sachposten gesetzt, Debitorengruppe bei {group}. "
        "Analytics dimensionSetEntries liefert in diesem Mandanten keine Zeilen und damit keine "
        "Zuordnung. Analytics dimensions beschreibt nur die Shortcut-Einrichtung, eine Zeile für "
        "die Firma, nicht den einzelnen Sachposten."
    )
    others = [
        route
        for route in candidates
        if route.key != chosen.key
        and route.with_department == chosen.with_department
        and route.with_customer_group == chosen.with_customer_group
    ]
    if others:
        other = others[0]
        paragraph += (
            f" {ROUTE_TITLE[other.key]} erreicht dieselbe Abdeckung in "
            f"{fmt_seconds(other.seconds)}. Die Zuordnung läuft dort über {JOIN_TEXT[other.key]}."
        )
    return chosen.key, paragraph


def propose_report_month(rows: Sequence[GlRow], as_of: date) -> tuple[int, int] | None:
    months = sorted(
        {
            (row.posting_date.year, row.posting_date.month)
            for row in rows
            if row.posting_date is not None and row.posting_date <= as_of
        }
    )
    if not months:
        return None
    target = (as_of.year, as_of.month)
    if target in months:
        return target
    earlier = [item for item in months if item <= target]
    return earlier[-1] if earlier else months[-1]


def prior_year_available(rows: Sequence[GlRow], year: int, month: int) -> bool:
    return any(
        row.posting_date is not None
        and row.posting_date.year == year - 1
        and row.posting_date.month == month
        for row in rows
    )


def render_profile(profile: Profile) -> str:
    lines = [
        "# Datenprofil CRONUS DE",
        "",
        f"Stand: {fmt_date(profile.stand)}. Laufdatum des Snapshots: {fmt_date(profile.run_day)}. "
        f"Stichtag: {fmt_date(profile.as_of)}.",
        "",
        "Der Stichtag ist ein Parameter. Ohne Angabe ist es der letzte Tag des Vormonats. "
        "Beträge sind EUR. Quelle sind GET-Aufrufe gegen die API v2.0 und "
        "microsoft/analytics/v1.0. Die Finance Reports API ist nicht aufgerufen.",
        "",
        "Sachposten in diesem Profil sind die Analytics-Entitäten "
        "incomeStatementGeneralLedgerEntries und balanceSheetGeneralLedgerEntries. "
        "Abschlussbuchungen (closingGeneralLedgerEntries): "
        f"{fmt_int(profile.closing_rows)} Zeilen.",
        "",
        "## Dimensionsrouten",
        "",
        "Frage: Welcher Weg liefert Abteilung und Debitorengruppe je Sachposten. "
        "Es wird noch nichts daraus gebaut.",
        "",
        _dimension_master_text(profile),
        "",
    ]
    for key in ROUTE_ORDER:
        route = next((item for item in profile.routes if item.key == key), None)
        if route is None:
            continue
        lines.extend(_render_route(route, profile))
    lines.extend(
        [
            "### Empfehlung",
            "",
            profile.recommendation,
            "",
            "## Bestand der Sachposten",
            "",
            f"Posten: {fmt_int(profile.gl_count)}. "
            f"Ältestes Buchungsdatum: {fmt_date(profile.oldest)}. "
            f"Jüngstes Buchungsdatum: {fmt_date(profile.newest)}. "
            f"Posten nach dem Stichtag: {fmt_int(profile.after_cutoff)}.",
        ]
    )
    if profile.after_cutoff:
        lines.append(
            "Diese Posten liegen zwischen "
            f"{fmt_date(profile.after_oldest)} und {fmt_date(profile.after_newest)}."
        )
    if profile.undated:
        lines.append(f"Posten ohne Buchungsdatum: {fmt_int(profile.undated)}.")
    lines.extend(
        [
            "",
            "Summe Soll ist die Summe der positiven amount. Summe Haben ist die Summe der "
            "Beträge der negativen amount. Der Saldo ist Summe Soll minus Summe Haben. "
            "Er ist 0,00, wenn Soll und Haben gleich sind. Die Abweichung ist dieser Saldo.",
            "",
            "### Nach Jahr",
            "",
            _period_table(profile.years, monthly=False),
            "",
            "### Nach Monat",
            "",
            _period_table(profile.months, monthly=True),
            "",
        ]
    )
    if profile.sign is not None:
        lines.extend(
            [
                "Gegenprobe mit v2.0 debitAmount minus creditAmount, verknüpft über die "
                f"Postennummer: {fmt_int(profile.sign.equal)} von {fmt_int(profile.sign.matched)} "
                "gemeinsamen Posten haben denselben Betrag auf 0,01 EUR. "
                f"Analytics-Posten: {fmt_int(profile.sign.analytics_rows)}. "
                f"v2.0-Posten: {fmt_int(profile.sign.v2_rows)}.",
                "",
            ]
        )
    lines.extend(_render_guv(profile))
    lines.extend(_render_open(profile))
    lines.extend(_render_trial(profile))
    lines.extend(_render_decisions(profile))
    lines.extend(["## Befunde", ""])
    if profile.findings_ok:
        lines.append("Ohne Abweichung:")
        lines.append("")
        lines.extend(f"- {item}" for item in profile.findings_ok)
        lines.append("")
    if profile.findings_diff:
        lines.append("Abweichungen:")
        lines.append("")
        lines.extend(f"- {item}" for item in profile.findings_diff)
        lines.append("")
    text = without_long_dashes("\n".join(lines).rstrip() + "\n")
    assert_no_secrets(text, ())
    return text


def write_snapshot_table(
    folder: Path,
    stem: str,
    rows: Sequence[Mapping[str, Any]],
    columns: Sequence[str],
) -> dict[str, Any]:
    """Write one parquet file and a 100-row CSV sample."""
    import pandas as pd

    folder.mkdir(parents=True, exist_ok=True)
    prepared = [{column: _snapshot_cell(row.get(column)) for column in columns} for row in rows]
    frame = pd.DataFrame(prepared, columns=list(columns))
    parquet_name = f"{stem}.parquet"
    csv_name = f"{stem}.sample.csv"
    frame.to_parquet(folder / parquet_name, index=False)
    frame.head(100).to_csv(folder / csv_name, index=False, encoding="utf-8")
    return {"rows": len(frame), "parquet": parquet_name, "csvSample": csv_name}


def write_manifest(folder: Path, document: Mapping[str, Any], needles: Sequence[str]) -> None:
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    assert_no_secrets(text, needles)
    folder.mkdir(parents=True, exist_ok=True)
    folder.joinpath("manifest.json").write_text(text, encoding="utf-8")


def scan_tree(folder: Path, needles: Sequence[str]) -> None:
    if not folder.exists():
        return
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        blob = path.read_bytes()
        for needle in needles:
            if needle and needle.encode("utf-8") in blob:
                raise RuntimeError("A snapshot file contains a forbidden identifier.")


def _render_entity(
    entity_set: str,
    catalog_key: str | None,
    model: MetadataModel | None,
) -> list[str]:
    lines = [f"### {entity_set}", ""]
    info = None if model is None else model.entities.get(entity_set)
    if info is None:
        lines.extend(
            [
                "Im $metadata gibt es keine EntitySet-Definition für diesen Namen.",
                "",
            ]
        )
        return lines
    keys = ", ".join(info.keys) if info.keys else "kein Schlüssel im Schema"
    lines.append(f"EntityType: {info.type_name}. Schlüssel: {keys}.")
    if catalog_key and catalog_key not in info.keys:
        lines.append(
            f"Der Katalog nennt {catalog_key}. Das steht so nicht als alleiniger Schema-Schlüssel."
        )
    elif catalog_key is None and info.keys:
        lines.append("Der Katalog lässt den Schlüssel leer. Das Schema nennt den Schlüssel oben.")
    lines.append("")
    lines.append(
        md_table(
            ("Feld", "Typ", "Nullable", "Schlüssel"),
            [
                (field.name, field.type_name, field.nullable, "ja" if field.key else "nein")
                for field in info.fields
            ],
        )
    )
    lines.append("")
    if info.navigation:
        lines.append("Navigationen:")
        lines.append("")
        nav_rows = [(item.name, item.type_name) for item in info.navigation]
        lines.append(md_table(("Name", "Typ"), nav_rows))
        lines.append("")
    return lines


def _enum_members(type_name: str, model: MetadataModel) -> tuple[str, ...] | None:
    base = type_name.split(",")[0].strip()
    if base.startswith("Edm.") or base.startswith("Collection("):
        return None
    short = base.rsplit(".", 1)[-1]
    return model.enums.get(base) or model.enums.get(short)


def _render_route(route: RouteAssessment, profile: Profile) -> list[str]:
    works = "ja" if route.works else "nein"
    status = route.http_status if route.http_status is not None else "kein Status"
    lines = [
        f"### {ROUTE_TITLE[route.key]}",
        "",
        f"Funktioniert: {works}. HTTP {status}. "
        f"Laufzeit: {fmt_seconds(route.seconds)}. Zeilen der Route: {fmt_int(route.rows)}.",
        "",
        f"Zuordnung: {JOIN_TEXT[route.key]}.",
        "",
    ]
    if route.per_entry:
        scope = "Sachposten (GuV und Bilanz)"
        if route.key == "expand" and not route.complete:
            scope = "Posten der Stichprobe"
        lines.append(
            "Abdeckung Abteilung: "
            f"{fmt_share(route.with_department, route.population)}. "
            "Abdeckung Debitorengruppe: "
            f"{fmt_share(route.with_customer_group, route.population)}. "
            f"Bezugsmenge: {fmt_int(route.population)} {scope}."
        )
        lines.append("")
        if route.key == "expand" and not route.complete:
            lines.append(
                "Die Abdeckung ist nur die Stichprobe. Der vollständige Lauf war von der "
                "Laufzeit her nicht vertretbar oder ist fehlgeschlagen."
            )
            lines.append("")
    if route.detail:
        lines.append(route.detail)
        lines.append("")
    if route.key == "expand" and profile.join is not None:
        join = profile.join
        lines.append(
            f"Gemeinsame Postennummern: {fmt_int(join.intersection)}. "
            f"Nur Analytics: {fmt_int(join.analytics_only)}. "
            f"Nur v2.0: {fmt_int(join.v2_only)}. "
            f"Doppelte Nummern Analytics: {fmt_int(join.duplicate_analytics)}. "
            f"Doppelte Nummern v2.0: {fmt_int(join.duplicate_v2)}."
        )
        lines.append("")
    if route.key == "shortcut":
        if profile.shortcuts:
            lines.append(
                md_table(
                    ("Platz", "Code", "Name", "Beschriftung"),
                    [
                        (item.index, item.code, item.name, item.caption)
                        for item in profile.shortcuts
                    ],
                )
            )
        else:
            lines.append("Die Zeile hat keine belegten Shortcut-Plätze.")
        lines.append("")
    if route.key == "set_entries":
        stats = profile.set_ids
        lines.append(
            f"Sachposten: {fmt_int(stats.entries)}. Davon dimensionSetID 0: {fmt_int(stats.zero)}. "
            f"Davon ungleich 0: {fmt_int(stats.nonzero)} "
            f"in {fmt_int(stats.distinct_nonzero)} verschiedenen IDs. "
            f"Diese IDs in dimensionSetEntries: {fmt_int(stats.matched_set_entries)}. "
            f"Diese IDs in dynamicDimensions: {fmt_int(stats.matched_dynamic)}."
        )
        lines.append("")
        lines.append(
            "Microsoft Learn beschreibt GET dimensionSetEntries ohne Pflichtfilter. "
            "Das Beispiel enthält eine Zeile mit dimensionSetID und den Plätzen dimension1 bis "
            "dimension8. Der Aufruf hier ist dieser GET. Zusätzliche Filter sind unten geprüft, "
            "falls die leere Menge am Filter gelegen hätte."
        )
        lines.append("")
        if profile.filter_probes:
            lines.append(
                md_table(
                    ("Filter", "HTTP", "Anzahl", "Fehler"),
                    [
                        (
                            item.expression or "ohne Filter",
                            "" if item.status is None else str(item.status),
                            "" if item.count is None else fmt_int(item.count),
                            item.error,
                        )
                        for item in profile.filter_probes
                    ],
                )
            )
            lines.append("")
    if route.key == "dynamic" and profile.dimension_entity_sets:
        listed = ", ".join(profile.dimension_entity_sets)
        lines.append(f"EntitySets mit dimension im Namen: {listed}.")
        lines.append("")
    return lines


def _dimension_master_text(profile: Profile) -> str:
    if not profile.masters:
        return "Der Dimensionsstamm aus v2.0 dimensions ist leer."
    lines = [
        "Dimensionsstamm v2.0, ohne technische IDs:",
        "",
        md_table(
            ("Code", "Name", "Werte"),
            [(item.code, item.name, fmt_int(item.value_count)) for item in profile.masters],
        ),
        "",
    ]
    if profile.department_codes:
        lines.append(
            "Als Abteilung gelesen: " + ", ".join(profile.department_codes) + "."
        )
    else:
        lines.append("Im Stamm gibt es keine Dimension, deren Code oder Name Abteilung ist.")
    if profile.customer_group_codes:
        lines.append(
            "Als Debitorengruppe gelesen: " + ", ".join(profile.customer_group_codes) + "."
        )
    else:
        lines.append(
            "Im Stamm gibt es keine Dimension, deren Code oder Name Debitorengruppe "
            "oder Kundengruppe ist."
        )
    if profile.department_values:
        lines.append("Werte Abteilung: " + ", ".join(profile.department_values) + ".")
    if profile.customer_group_values:
        lines.append("Werte Debitorengruppe: " + ", ".join(profile.customer_group_values) + ".")
    return "\n".join(lines)


def _period_table(rows: Sequence[PeriodTotal], *, monthly: bool) -> str:
    rendered = []
    debit = Decimal(0)
    credit = Decimal(0)
    count = 0
    for row in rows:
        debit += row.debit
        credit += row.credit
        count += row.count
        label = fmt_month(row.year, row.month) if monthly and row.month else str(row.year)
        rendered.append(
            (
                label,
                fmt_int(row.count),
                fmt_money(row.debit),
                fmt_money(row.credit),
                fmt_money(row.balance),
            )
        )
    rendered.append(
        ("Gesamt", fmt_int(count), fmt_money(debit), fmt_money(credit), fmt_money(debit - credit))
    )
    header = ("Monat" if monthly else "Jahr", "Posten", "Summe Soll", "Summe Haben", "Saldo")
    return md_table(header, rendered)


def _render_guv(profile: Profile) -> list[str]:
    lines = [
        "## GuV nach Kontenkategorie und Jahr",
        "",
        "Nur GuV-Sachposten. Das Feld amount bleibt im Soll positiv und im Haben negativ. "
        "Saldo BC ist die Summe amount. Saldo GuV ist die Summe von minus amount. "
        "Einnahmen, die im Haben gebucht sind, werden im Saldo GuV positiv.",
        "",
        f"Kategorie aus {profile.category_source}. Kontonummer der GuV-Posten ist accountNo, "
        "verknüpft mit der Kontonummer im Kontenplan.",
        "",
    ]
    if not profile.categories:
        lines.extend(["Keine GuV-Posten mit Buchungsdatum.", ""])
        return lines
    lines.append(
        md_table(
            ("Kategorie", "Jahr", "Posten", "Saldo BC", "Saldo GuV", "Summe Soll", "Summe Haben"),
            [
                (
                    row.category,
                    "gesamt" if row.year is None else str(row.year),
                    fmt_int(row.count),
                    fmt_money(row.balance_bc),
                    fmt_money(row.balance_guv),
                    fmt_money(row.debit),
                    fmt_money(row.credit),
                )
                for row in _with_category_totals(profile.categories)
            ],
        )
    )
    lines.append("")
    lines.extend(_render_anomaly(profile))
    lines.extend(
        [
            "## Konten ohne Kategorie",
            "",
            "Liste der Konten, deren Feld category in der API v2.0 leer ist. "
            "Summe ist die Summe amount aller Sachposten des Kontos, GuV und Bilanz. "
            "Konten mit Posten, die im Kontenplan fehlen, stehen mit leerem Namen dabei.",
            "",
        ]
    )
    if not profile.uncategorized:
        lines.append("Kein Konto ohne Kategorie.")
        lines.append("")
    else:
        lines.append(
            md_table(
                ("Nummer", "Name", "Kategorie v2.0", "Kategorie Analytics", "Summe"),
                [
                    (
                        row.number,
                        row.name,
                        row.category,
                        row.analytics_category,
                        fmt_money(row.total),
                    )
                    for row in profile.uncategorized
                ],
            )
        )
        lines.append("")
    if profile.watch:
        lines.append(
            "Die Datenlage nennt 0210, 0280, 1085, 2720 und 4091 als Beispiele ohne Kategorie. "
            "Stand in diesem Lauf:"
        )
        lines.append("")
        lines.append(
            md_table(
                (
                    "Nummer",
                    "Name",
                    "Kategorie v2.0",
                    "Unterkategorie",
                    "Kategorie Analytics",
                    "Summe",
                ),
                [
                    (
                        row.number,
                        row.name,
                        row.category,
                        row.subcategory,
                        row.analytics_category,
                        fmt_money(row.total),
                    )
                    for row in profile.watch
                ],
            )
        )
        lines.append("")
    return lines


def _render_anomaly(profile: Profile) -> list[str]:
    income = _kind_totals(profile.categories, "income")
    cogs = _kind_totals(profile.categories, "cogs")
    lines = ["### Wareneinsatz und Einnahmen", ""]
    if income is None and cogs is None:
        lines.append(
            "Weder eine Kategorie Einnahmen noch eine Kategorie Wareneinsatz ist in den "
            "GuV-Posten getroffen."
        )
        lines.append("")
        return lines
    if income is not None:
        lines.append(
            f"Kategorie {income.category}: {fmt_int(income.count)} Posten, "
            f"Saldo BC {fmt_money(income.balance_bc)}, Saldo GuV {fmt_money(income.balance_guv)}."
        )
    if cogs is not None:
        side = "Haben" if cogs.balance_bc < 0 else "Soll" if cogs.balance_bc > 0 else "ausgeglichen"
        lines.append(
            f"Kategorie {cogs.category}: {fmt_int(cogs.count)} Posten, "
            f"Saldo BC {fmt_money(cogs.balance_bc)}, Saldo GuV {fmt_money(cogs.balance_guv)}. "
            f"Der Gesamtsaldo liegt im {side}."
        )
    if income is not None and cogs is not None:
        lines.append(
            f"Betrag des Saldos GuV der Einnahmen: {fmt_money(abs(income.balance_guv))}. "
            f"Betrag des Saldos BC des Wareneinsatzes: {fmt_money(abs(cogs.balance_bc))}."
        )
    lines.append("Das ist die Beschreibung der Summen, ohne Deutung.")
    lines.append("")
    if profile.subcategories:
        lines.append("Unterkategorien dieser beiden Kategorien, alle Jahre zusammen:")
        lines.append("")
        lines.append(
            md_table(
                ("Kategorie", "Unterkategorie", "Posten", "Saldo BC", "Saldo GuV"),
                [
                    (
                        row.category,
                        row.subcategory,
                        fmt_int(row.count),
                        fmt_money(row.balance_bc),
                        fmt_money(row.balance_guv),
                    )
                    for row in profile.subcategories
                ],
            )
        )
        lines.append("")
    return lines


def _render_open(profile: Profile) -> list[str]:
    return [
        "## Debitoren und Kreditoren zum Stichtag",
        "",
        "Der Restbetrag eines Postens ist die Summe der Detailbeträge mit Buchungsdatum bis "
        f"zum {fmt_date(profile.as_of)}. Debitoren: dcleAmountLCY je cleEntryNo. "
        "Kreditoren: dvleAmountLCY je vleEntryNo. Ein Posten ist offen, wenn der Restbetrag "
        "auf 0,01 EUR ungleich 0,00 ist. Die Kennzeichen cleOpen und vleOpen "
        "werden nicht verwendet.",
        "",
        md_table(
            ("Seite", "Offene Posten", "Debitoren oder Kreditoren", "Summe offen"),
            [
                (
                    "Debitoren",
                    fmt_int(profile.customers.entries),
                    fmt_int(profile.customers.parties),
                    fmt_money(profile.customers.amount),
                ),
                (
                    "Kreditoren",
                    fmt_int(profile.vendors.entries),
                    fmt_int(profile.vendors.parties),
                    fmt_money(profile.vendors.amount),
                ),
            ],
        ),
        "",
    ]


def _render_trial(profile: Profile) -> list[str]:
    lines = [
        "## Vorabprüfung gegen die Saldenliste",
        "",
        "Abruf: API v2.0 trialBalances mit dateFilter für den 31.12.2025, den 30.06.2026 und "
        f"den Stichtag {fmt_date(profile.as_of)}. "
        "Nettobewegung im Snapshot ist die Summe amount der Sachposten mit Buchungsdatum bis "
        "zum jeweiligen Datum, je Kontonummer. "
        "Nettoveränderung der Saldenliste ist totalDebit minus totalCredit. "
        "Saldo zum Stichtag ist balanceAtDateDebit minus balanceAtDateCredit. "
        "Verglichen werden Buchungskonten und Konten mit Sachposten. "
        "Summen- und Überschriftskonten stehen getrennt, weil sie in der "
        "Saldenliste die Einzelkonten noch einmal enthalten können.",
        "",
    ]
    if profile.trial_error:
        lines.append(f"Der Abruf der Saldenliste ist fehlgeschlagen: {profile.trial_error}")
        lines.append("")
        if not profile.trials:
            return lines
    if profile.trial_same_signature:
        lines.append(
            "Die drei Abrufe haben dieselben Summen über alle Saldenzeilen. "
            "Der dateFilter hat die Beträge in diesem Lauf nicht sichtbar getrennt."
        )
        lines.append("")
    for trial in profile.trials:
        lines.extend(_render_one_trial(trial))
    return lines


def _render_one_trial(trial: TrialComparison) -> list[str]:
    lines = [
        f"### {fmt_date(trial.as_of)}",
        "",
        f"Zeilen der Saldenliste: {fmt_int(trial.row_count)}. "
        f"Buchungskonten im Vergleich: {fmt_int(trial.posting_compared)}. "
        f"Davon Nettoveränderung gleich kumulierte Nettobewegung: "
        f"{fmt_int(trial.change_zero)}. "
        f"Davon Saldo zum Stichtag gleich kumulierte Nettobewegung: "
        f"{fmt_int(trial.balance_zero)}. "
        f"Davon Nettoveränderung gleich Bewegung nur an diesem Tag: {fmt_int(trial.day_zero)}.",
        "",
        "Summen der verglichenen Buchungskonten: "
        f"Snapshot {fmt_money(trial.snapshot_sum)}, "
        f"Nettoveränderung {fmt_money(trial.trial_change_sum)}, "
        f"Saldo zum Stichtag {fmt_money(trial.trial_balance_sum)}.",
        "",
    ]
    if trial.posting_compared and trial.balance_zero == trial.posting_compared:
        lines.append(
            "Der Saldo zum Stichtag ist auf jedem verglichenen Buchungskonto gleich "
            "der kumulierten Nettobewegung."
        )
    if (
        trial.posting_compared
        and trial.day_zero == trial.posting_compared
        and trial.change_zero != trial.posting_compared
    ):
        lines.append(
            "Die Nettoveränderung totalDebit minus totalCredit ist auf jedem "
            "Buchungskonto gleich der Bewegung nur an diesem Tag."
        )
    if trial.echoed:
        lines.append("Zurückgegebener dateFilter: " + ", ".join(trial.echoed) + ".")
        lines.append("")
    lines.append(
        "Differenzliste der Buchungskonten. Eine Zeile steht hier, wenn Nettoveränderung "
        "oder Saldo zum Stichtag von der kumulierten Nettobewegung abweicht. "
        "Differenz Nettoveränderung ist Saldenliste minus Snapshot. "
        "Differenz Saldo ist Saldo zum Stichtag minus Snapshot."
    )
    lines.append("")
    if not trial.posting_diffs:
        lines.append("Keine Differenz auf Buchungskonten.")
        lines.append("")
    else:
        lines.append(
            md_table(
                (
                    "Konto",
                    "Name",
                    "Snapshot",
                    "Nettoveränderung",
                    "Differenz Nettoveränderung",
                    "Saldo zum Stichtag",
                    "Differenz Saldo",
                ),
                [
                    (
                        row.number,
                        row.name,
                        fmt_money(row.snapshot_net),
                        fmt_money(row.net_change),
                        fmt_money(row.diff_change),
                        fmt_money(row.balance_at),
                        fmt_money(row.diff_balance),
                    )
                    for row in trial.posting_diffs
                ],
            )
        )
        lines.append("")
    if trial.other_diffs:
        lines.append(
            "Summen- und Überschriftskonten mit Betrag ungleich 0,00. "
            "Sie sind nicht Teil der Postenabstimmung."
        )
        lines.append("")
        lines.append(
            md_table(
                ("Konto", "Name", "Kontoart", "Nettoveränderung", "Saldo zum Stichtag"),
                [
                    (
                        row.number,
                        row.name,
                        row.account_type,
                        fmt_money(row.net_change),
                        fmt_money(row.balance_at),
                    )
                    for row in trial.other_diffs
                ],
            )
        )
        lines.append("")
    return lines


def _render_decisions(profile: Profile) -> list[str]:
    if profile.report_month is None:
        month_text = "kein Monat mit Posten bis zum Stichtag"
        prior = "nein"
    else:
        year, month = profile.report_month
        month_text = fmt_month(year, month)
        prior = "ja" if profile.prior_year else "nein"
    budget = "ja" if profile.budget_rows or profile.budget_entry_rows else "nein"
    if profile.department_codes:
        cost = profile.department_codes[0]
        cost_text = (
            f"{cost}. Die Dimension steht im Stamm. Ob sie je Posten ankommt, steht in der "
            "Empfehlung zur Dimensionsroute."
        )
    else:
        cost_text = "offen, im Stamm ist keine Abteilung erkannt."
    return [
        "## Vorschläge",
        "",
        f"Berichtsmonat: {month_text}. Das ist der jüngste Monat bis zum Stichtag mit Posten. "
        "Der laufende Monat nach dem Stichtag ist nicht der Berichtsmonat.",
        "",
        f"Vorjahr verfügbar: {prior}. Geprüft ist derselbe Kalendermonat im Vorjahr.",
        "",
        f"Budget vorhanden: {budget}. generalLedgerBudgets hat {fmt_int(profile.budget_rows)} "
        f"Zeilen, generalLedgerBudgetEntries hat {fmt_int(profile.budget_entry_rows)} Zeilen.",
        "",
        f"Kostenstelle: {cost_text}",
        "",
        "Das sind Vorschläge. Die Bestätigung kommt von Mirza.",
        "",
    ]


def build_profile(
    *,
    stand: date,
    as_of: date,
    run_day: date,
    gl_rows: Sequence[GlRow],
    accounts: Sequence[AccountInfo],
    customers: OpenTotal,
    vendors: OpenTotal,
    routes: Sequence[RouteAssessment],
    masters: Sequence[DimensionMaster],
    department_values: Sequence[str],
    customer_group_values: Sequence[str],
    join: JoinStats | None,
    set_ids: SetIdStats,
    filter_probes: Sequence[FilterProbe],
    shortcuts: Sequence[ShortcutSlot],
    trials: Sequence[TrialComparison],
    trial_error: str,
    budget_rows: int,
    budget_entry_rows: int,
    closing_rows: int,
    sign: SignCheck | None,
    category_source: str,
    dimension_entity_sets: Sequence[str],
) -> Profile:
    dated = [row for row in gl_rows if row.posting_date is not None]
    after = [row for row in dated if row.posting_date and row.posting_date > as_of]
    account_map = {account.number: account for account in accounts}
    categories = tuple(category_totals(gl_rows, account_map))
    subs = tuple(subcategory_totals(gl_rows, account_map))
    totals = account_totals(gl_rows)
    departments, groups = classify_dimensions(masters)
    key, paragraph = recommend(routes)
    report_month = propose_report_month(gl_rows, as_of)
    prior = False
    if report_month is not None:
        prior = prior_year_available(gl_rows, report_month[0], report_month[1])
    same = len({item.signature for item in trials}) <= 1 and len(trials) > 1
    years = tuple(period_totals(gl_rows, monthly=False))
    months = tuple(period_totals(gl_rows, monthly=True))
    oldest = min((row.posting_date for row in dated), default=None)
    newest = max((row.posting_date for row in dated), default=None)
    profile = Profile(
        stand=stand,
        as_of=as_of,
        run_day=run_day,
        gl_count=len(gl_rows),
        undated=len(gl_rows) - len(dated),
        oldest=oldest,
        newest=newest,
        after_cutoff=len(after),
        after_oldest=min((row.posting_date for row in after), default=None),
        after_newest=max((row.posting_date for row in after), default=None),
        years=years,
        months=months,
        sign=sign,
        category_source=category_source,
        categories=categories,
        subcategories=subs,
        uncategorized=tuple(accounts_without_category(accounts, totals)),
        watch=tuple(watch_accounts(accounts, totals)),
        customers=customers,
        vendors=vendors,
        routes=tuple(routes),
        masters=tuple(masters),
        department_codes=departments,
        customer_group_codes=groups,
        department_values=tuple(department_values),
        customer_group_values=tuple(customer_group_values),
        join=join,
        set_ids=set_ids,
        filter_probes=tuple(filter_probes),
        shortcuts=tuple(shortcuts),
        trials=tuple(trials),
        trial_error=trial_error,
        trial_same_signature=same,
        budget_rows=budget_rows,
        budget_entry_rows=budget_entry_rows,
        closing_rows=closing_rows,
        recommendation_key=key,
        recommendation=paragraph,
        report_month=report_month,
        prior_year=prior,
        dimension_entity_sets=tuple(dimension_entity_sets),
        findings_ok=(),
        findings_diff=(),
    )
    ok, diff = _findings(profile)
    return replace(profile, findings_ok=ok, findings_diff=diff)


def _findings(profile: Profile) -> tuple[tuple[str, ...], tuple[str, ...]]:
    ok: list[str] = []
    diff: list[str] = []
    if profile.years:
        balance = sum((row.balance for row in profile.years), Decimal(0))
        text = f"Saldo Soll minus Haben über alle datierten Sachposten: {fmt_money(balance)}."
        (ok if cents(balance) == 0 else diff).append(text)
    else:
        diff.append("Keine datierten Sachposten.")
    for row in profile.years:
        if cents(row.balance) != 0:
            diff.append(f"Saldo {row.year}: {fmt_money(row.balance)}.")
    sign = profile.sign
    if sign is not None and sign.matched and sign.equal == sign.matched:
        ok.append("amount entspricht bei allen gemeinsamen Posten debitAmount minus creditAmount.")
    elif profile.sign is not None and profile.sign.matched != profile.sign.equal:
        diff.append(
            "amount und debitAmount minus creditAmount weichen bei "
            f"{fmt_int(profile.sign.matched - profile.sign.equal)} gemeinsamen Posten ab."
        )
    if profile.join is not None and profile.join.analytics_only == 0 and profile.join.v2_only == 0:
        ok.append("Die Postennummern von Analytics und v2.0 decken sich.")
    elif profile.join is not None and (profile.join.analytics_only or profile.join.v2_only):
        diff.append(
            "Postennummern ohne Gegenstück: "
            f"Analytics {fmt_int(profile.join.analytics_only)}, "
            f"v2.0 {fmt_int(profile.join.v2_only)}."
        )
    if profile.uncategorized:
        diff.append(f"Konten ohne Kategorie in v2.0: {fmt_int(len(profile.uncategorized))}.")
    else:
        ok.append("Jedes Konto im v2.0-Kontenplan hat eine Kategorie.")
    income = _kind_totals(profile.categories, "income")
    cogs = _kind_totals(profile.categories, "cogs")
    if cogs is not None and cogs.balance_bc < 0:
        diff.append(
            f"Kategorie {cogs.category}: Gesamtsaldo BC {fmt_money(cogs.balance_bc)} im Haben."
        )
    if income is not None and cogs is not None and abs(income.balance_guv) < abs(cogs.balance_bc):
        diff.append(
            f"Betrag der Einnahmen ({fmt_money(abs(income.balance_guv))} Saldo GuV) liegt unter "
            f"dem Betrag des Wareneinsatzes ({fmt_money(abs(cogs.balance_bc))} Saldo BC)."
        )
    if profile.after_cutoff:
        diff.append(
            f"Posten nach dem Stichtag: {fmt_int(profile.after_cutoff)}, "
            f"{fmt_date(profile.after_oldest)} bis {fmt_date(profile.after_newest)}."
        )
    for trial in profile.trials:
        gaps = trial.posting_compared - trial.balance_zero
        change_gaps = trial.posting_compared - trial.change_zero
        if gaps == 0 and change_gaps == 0:
            ok.append(f"Saldenliste {fmt_date(trial.as_of)}: keine Differenz auf Buchungskonten.")
        else:
            diff.append(
                f"Saldenliste {fmt_date(trial.as_of)}: {fmt_int(change_gaps)} Konten mit Differenz "
                f"bei der Nettoveränderung, {fmt_int(gaps)} Konten mit Differenz "
                "beim Saldo zum Stichtag."
            )
    if profile.trial_same_signature and profile.trials:
        diff.append("Die drei dateFilter liefern dieselben Summen der Saldenliste.")
    if profile.trial_error:
        diff.append("Saldenliste nicht vergleichbar, der Abruf ist fehlgeschlagen.")
    empty_sets = next(
        (item for item in profile.routes if item.key == "set_entries" and not item.works),
        None,
    )
    if empty_sets is not None:
        diff.append("Analytics dimensionSetEntries hat keine Zeilen.")
    if profile.budget_rows == 0 and profile.budget_entry_rows == 0:
        ok.append("Kein Sachkontenbudget.")
    return tuple(ok), tuple(diff)


def _with_category_totals(rows: Sequence[CategoryTotal]) -> list[CategoryTotal]:
    grouped: dict[str, list[CategoryTotal]] = defaultdict(list)
    for row in rows:
        grouped[row.category].append(row)
    ordered: list[CategoryTotal] = []
    for category in sorted(grouped, key=_category_rank):
        items = grouped[category]
        ordered.extend(items)
        ordered.append(
            CategoryTotal(
                category,
                "",
                None,
                sum(item.count for item in items),
                sum((item.balance_bc for item in items), Decimal(0)),
                sum((item.debit for item in items), Decimal(0)),
                sum((item.credit for item in items), Decimal(0)),
            )
        )
    return ordered


def _kind_totals(rows: Sequence[CategoryTotal], kind: str) -> CategoryTotal | None:
    picked = [row for row in rows if _category_kind(row.category) == kind]
    if not picked:
        return None
    return CategoryTotal(
        picked[0].category,
        "",
        None,
        sum(item.count for item in picked),
        sum((item.balance_bc for item in picked), Decimal(0)),
        sum((item.debit for item in picked), Decimal(0)),
        sum((item.credit for item in picked), Decimal(0)),
    )


def _category_kind(name: str) -> str:
    token = name.casefold().strip()
    if token in INCOME_NAMES:
        return "income"
    if token in COGS_NAMES:
        return "cogs"
    return ""


def _category_rank(name: str) -> tuple[int, str]:
    order = {
        "income": 0,
        "cogs": 1,
    }
    kind = _category_kind(name)
    if name.casefold() == "ohne kategorie":
        return (9, name.casefold())
    return (order.get(kind, 5), name.casefold())


def _diff_sort(row: DiffRow) -> tuple[Decimal, str]:
    magnitude = max(abs(cents(row.diff_change)), abs(cents(row.diff_balance)))
    return (-magnitude, row.number)


def _number_index(numbers: Sequence[str]) -> tuple[dict[str, str], dict[str, str]]:
    exact = {number: number for number in numbers if number}
    loose: dict[str, list[str]] = defaultdict(list)
    for number in exact:
        loose[loose_number(number)].append(number)
    unique = {key: values[0] for key, values in loose.items() if len(values) == 1}
    return exact, unique


def _resolve_number(number: str, exact: Mapping[str, str], unique_loose: Mapping[str, str]) -> str:
    if number in exact:
        return exact[number]
    found = unique_loose.get(loose_number(number))
    return found or number


def _snapshot_cell(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, float):
        return format(Decimal(str(value)), "f")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (dict, list)):
        return ""
    return value


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _qualified(element: ET.Element, name: str) -> str:
    namespace = ""
    parent_schema = None
    # EntityType does not carry the schema namespace attribute. Callers also index the short name.
    if parent_schema is not None:
        namespace = parent_schema
    return f"{namespace}.{name}" if namespace else name


def _parse_entity_type(element: ET.Element) -> dict[str, Any]:
    keys: list[str] = []
    fields: list[tuple[str, str, str, str]] = []
    navigation: list[tuple[str, str]] = []
    base = element.attrib.get("BaseType", "")
    for child in list(element):
        local = _local(child.tag)
        if local == "Key":
            keys.extend(
                item.attrib.get("Name", "")
                for item in list(child)
                if _local(item.tag) == "PropertyRef" and item.attrib.get("Name")
            )
        elif local == "Property":
            nullable = child.attrib.get("Nullable")
            nullable_text = "nein" if nullable is not None and nullable.lower() == "false" else "ja"
            extra = _type_extra(child)
            fields.append(
                (
                    child.attrib.get("Name", ""),
                    child.attrib.get("Type", ""),
                    nullable_text,
                    extra,
                )
            )
        elif local == "NavigationProperty":
            navigation.append((child.attrib.get("Name", ""), child.attrib.get("Type", "")))
    return {"base": base, "keys": keys, "fields": fields, "navigation": navigation}


def _resolve_type(type_ref: str, types: Mapping[str, dict[str, Any]]) -> dict[str, Any] | None:
    short = type_ref.rsplit(".", 1)[-1]
    parsed = types.get(type_ref) or types.get(short)
    if parsed is None:
        return None
    fields = list(parsed["fields"])
    keys = list(parsed["keys"])
    navigation = list(parsed["navigation"])
    base_name = str(parsed.get("base") or "")
    seen = {type_ref, short}
    while base_name and base_name not in seen:
        seen.add(base_name)
        base = types.get(base_name) or types.get(base_name.rsplit(".", 1)[-1])
        if base is None:
            break
        fields = list(base["fields"]) + fields
        keys = list(base["keys"]) + keys
        navigation = list(base["navigation"]) + navigation
        base_name = str(base.get("base") or "")
    return {"keys": keys, "fields": fields, "navigation": navigation}


def _type_extra(element: ET.Element) -> str:
    parts: list[str] = []
    max_length = element.attrib.get("MaxLength")
    if max_length and max_length.lower() != "max":
        parts.append(f"Länge {max_length}")
    scale = element.attrib.get("Scale")
    if scale and scale.lower() not in {"variable", "floating"}:
        parts.append(f"Dezimalstellen {scale}")
    return ", ".join(parts)


def _decorate_type(type_name: str, extra: str) -> str:
    short = _short_type(type_name)
    if extra:
        return f"{short}, {extra}"
    return short


def _short_type(type_name: str) -> str:
    if type_name.startswith("Collection(") and type_name.endswith(")"):
        inner = type_name[len("Collection(") : -1]
        return f"Collection({_short_type(inner)})"
    if type_name.startswith("Edm."):
        return type_name
    return type_name.rsplit(".", 1)[-1]
