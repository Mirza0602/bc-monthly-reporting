"""P1 to P9 on a snapshot. No network.

Periods come from ending balances. Month = ending balance minus the previous
month end. YTD = ending balance minus 31.12. of the prior year. Account 5021
is the net movement. Receipt clearing is removed using item value entries
(Positive Adjmt. and Output), with the sign of the credit side. GuV ending
balances are not used as period amounts.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from src.datenbestand import (
    assert_no_secrets,
    cents,
    fmt_date,
    fmt_money,
    fmt_share,
    is_posting_type,
    norm_key,
    parse_iso_date,
    readable_token,
)
from src.trial_balance import (
    is_calendar_month,
    latest_snapshot,
    month_end,
    parse_amount,
    shift_month,
)

BUCKETS = (
    "UMSATZ",
    "WARENEINSATZ",
    "LAGERZUGANG_VERRECHNUNG",
    "BETRIEBSAUFWAND",
    "ABSCHREIBUNG",
    "SONSTIGER_ERTRAG_AUFWAND",
    "ZINS_FINANZ",
    "STEUER",
    "NICHT_ZUGEORDNET",
)
BUCKET_LABEL = {
    "UMSATZ": "Umsatz",
    "WARENEINSATZ": "Wareneinsatz",
    "LAGERZUGANG_VERRECHNUNG": "Lagerzugang Verrechnung",
    "BETRIEBSAUFWAND": "Betriebsaufwand",
    "ABSCHREIBUNG": "Abschreibung",
    "SONSTIGER_ERTRAG_AUFWAND": "Sonstiger Ertrag und Aufwand",
    "ZINS_FINANZ": "Zins und Finanz",
    "STEUER": "Steuer",
    "NICHT_ZUGEORDNET": "Nicht zugeordnet",
}
EBIT_PLUS = frozenset({"UMSATZ", "SONSTIGER_ERTRAG_AUFWAND"})
EBIT_MINUS = frozenset({"WARENEINSATZ", "BETRIEBSAUFWAND", "ABSCHREIBUNG"})
BRIDGE_EXTRA = ("ZINS_FINANZ", "STEUER", "LAGERZUGANG_VERRECHNUNG", "NICHT_ZUGEORDNET")
RULES = frozenset({"NETTO", "NUR_SOLL", "NUR_HABEN"})
OPEN_THRESHOLD = Decimal("0.01")
MAPPING_COLUMNS = (
    "konto",
    "kontoname",
    "bucket",
    "regel",
    "vorzeichen",
    "quelle",
    "bemerkung",
)


@dataclass(frozen=True)
class MappingRow:
    account: str
    name: str
    bucket: str
    rule: str
    sign: int
    source: str
    note: str


@dataclass(frozen=True)
class AccountList:
    check_id: str
    numbers: tuple[str, ...]
    source: str
    status: str
    note: str
    expected: Decimal | None = None


@dataclass(frozen=True)
class KnownDifference:
    check_id: str
    amount: Decimal
    document: str
    item: str
    cause: str
    source: str
    status: str


@dataclass(frozen=True)
class Config:
    tolerance: Decimal
    stichtag: date | None
    receivables: AccountList
    payables: AccountList
    inventory: AccountList
    checks: tuple[tuple[str, str], ...]
    zero_accounts: AccountList | None = None
    known: tuple[KnownDifference, ...] = ()


@dataclass(frozen=True)
class BalanceCheck:
    account: str
    name: str
    gl_balance: Decimal
    trial_balance: Decimal
    expected: Decimal

    @property
    def difference(self) -> Decimal:
        return cents(self.trial_balance - self.expected)


@dataclass(frozen=True)
class VarianceLine:
    account: str
    name: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class GlEntry:
    entry_no: str
    account: str
    posting_date: date
    debit: Decimal
    credit: Decimal
    dimension_set_id: str = ""
    source_code: str = ""
    source_type: str = ""
    description: str = ""
    document_number: str = ""
    document_type: str = ""

    @property
    def amount(self) -> Decimal:
        return self.debit - self.credit


@dataclass(frozen=True)
class TrialPoint:
    account: str
    name: str
    account_type: str
    start: date
    end: date
    debit: Decimal
    credit: Decimal
    balance: Decimal


@dataclass(frozen=True)
class ChartAccount:
    number: str
    name: str
    account_type: str
    income_statement: bool
    category: str = ""
    subcategory: str = ""
    hierarchy: str = ""
    parent: str = ""
    subcategory_entry: int = 0


@dataclass(frozen=True)
class Detail:
    entry_no: str
    posting_date: date
    amount: Decimal


@dataclass(frozen=True)
class CostLine:
    posting_date: date
    cost_actual: Decimal
    cost_posted: Decimal = Decimal(0)
    item_ledger_type: str = ""
    document_type: str = ""
    document_number: str = ""
    entry_type: str = ""
    item_no: str = ""
    entry_no: str = ""
    ledger_entry_no: str = ""
    quantity: Decimal = Decimal(0)


@dataclass(frozen=True)
class SalesLine:
    posting_date: date
    sales_amount: Decimal
    cost_actual: Decimal
    cost_posted: Decimal = Decimal(0)


@dataclass(frozen=True)
class ItemRecord:
    number: str
    name: str
    item_type: str
    product_group: str
    inventory_group: str


@dataclass(frozen=True)
class DimensionLine:
    set_id: str
    code: str


@dataclass(frozen=True)
class CountRow:
    route: str
    entity: str
    snapshot_rows: int
    manifest_rows: int

    @property
    def difference(self) -> int:
        return self.snapshot_rows - self.manifest_rows


@dataclass
class Books:
    gl: tuple[GlEntry, ...] = ()
    trial: tuple[TrialPoint, ...] = ()
    chart: dict[str, ChartAccount] = field(default_factory=dict)
    customers: tuple[Detail, ...] = ()
    vendors: tuple[Detail, ...] = ()
    item_values: tuple[CostLine, ...] = ()
    item_ledger: tuple[CostLine, ...] = ()
    purchases: tuple[CostLine, ...] = ()
    sales: tuple[SalesLine, ...] = ()
    items: dict[str, ItemRecord] = field(default_factory=dict)
    dimensions: tuple[DimensionLine, ...] = ()
    counts: tuple[CountRow, ...] = ()
    closing_entries: frozenset[str] = frozenset()
    company: str = ""
    environment: str = ""
    stand: str = ""
    snapshot_name: str = ""
    snapshot_cutoff: date | None = None


@dataclass(frozen=True)
class Figure:
    report: Decimal
    reference: Decimal

    @property
    def difference(self) -> Decimal:
        return cents(self.report - self.reference)


@dataclass(frozen=True)
class AccountCheck:
    account: str
    name: str
    p2: Figure
    p3: Figure


@dataclass(frozen=True)
class Bridge:
    buckets: dict[str, Figure]
    ebit: Figure
    total: Figure
    guv: Figure

    @property
    def difference(self) -> Figure:
        return Figure(
            self.guv.report - self.total.report,
            self.guv.reference - self.total.reference,
        )


@dataclass(frozen=True)
class ValueBridge:
    sales_amount: Decimal
    sales_cost: Decimal
    revenue: Decimal
    cogs: Decimal
    account_4201: Decimal


@dataclass(frozen=True)
class DocumentGap:
    document: str
    posting_date: date
    gl_amount: Decimal
    ledger_amount: Decimal
    item_no: str
    entry_type: str
    item_ledger_type: str

    @property
    def difference(self) -> Decimal:
        return cents(self.gl_amount - self.ledger_amount)


@dataclass(frozen=True)
class MovementAccount:
    account: str
    name: str
    bucket: str
    rule: str


@dataclass
class Report:
    as_of: date
    generated_at: datetime
    company: str
    environment: str
    stand: str
    snapshot_name: str
    tolerance: Decimal
    receivables: AccountList
    payables: AccountList
    inventory: AccountList
    p1: Decimal
    p4_month: Figure
    p4_ytd: Figure
    p5_month: Figure
    p5_ytd: Figure
    p6: Figure
    p7: Figure
    p8: Figure
    p8_cost_gap: Decimal
    bridge_month: Bridge
    bridge_ytd: Bridge
    values_month: ValueBridge
    values_ytd: ValueBridge
    accounts: tuple[AccountCheck, ...]
    counts: tuple[CountRow, ...]
    after_protocol: int
    after_protocol_from: date | None
    after_protocol_to: date | None
    after_snapshot: int
    after_snapshot_from: date | None
    after_snapshot_to: date | None
    guv_entries: int
    with_department: int
    with_customer_group: int
    kpi_unassigned: dict[str, tuple[int, int, Decimal, Decimal]]
    credit_5021_2025: Decimal
    standard_credit: Decimal
    standard_lines: int
    standard_date: date | None
    value_groups_2025: tuple[tuple[str, str, int, Decimal, Decimal], ...]
    ledger_groups_2025: tuple[tuple[str, str, int, Decimal], ...]
    inventory_gaps: tuple[DocumentGap, ...]
    movement: tuple[MovementAccount, ...]
    category_notes: tuple[str, ...]
    p8_explained: bool
    zero_balances: tuple[BalanceCheck, ...] = ()
    variance_lines: tuple[VarianceLine, ...] = ()
    p5b: tuple[CostCheck, ...] = ()
    p8_status: str = ""
    p8_evidence: str = ""
    cogs_note: str = ""
    receipt_2025: Decimal = Decimal(0)
    revenue_cut_month: Figure | None = None
    revenue_cut_ytd: Figure | None = None
    known: tuple[KnownDifference, ...] = ()


@dataclass(frozen=True)
class CostCheck:
    label: str
    fibu: Decimal
    reference: Decimal

    @property
    def difference(self) -> Decimal:
        return cents(self.fibu - self.reference)


def plain(text: str) -> str:
    cleaned = str(text).replace("\u00a0", " ").replace("\u2013", "-").replace("\u2014", "-")
    return " ".join(cleaned.split())


def prior_month_end(day: date) -> date:
    year, month = shift_month(day.year, day.month, -1)
    return month_end(year, month)


def ytd_opening(day: date) -> date:
    return date(day.year - 1, 12, 31)


def months_through(day: date) -> tuple[date, ...]:
    return tuple(month_end(day.year, month) for month in range(1, day.month + 1))


def parse_month(value: str) -> date:
    text = value.strip()
    if len(text) == 7:
        year, month = text.split("-")
        return month_end(int(year), int(month))
    parsed = date.fromisoformat(text)
    if parsed != month_end(parsed.year, parsed.month):
        raise ValueError("month must be a month end.")
    return parsed


def within(difference: Decimal, tolerance: Decimal) -> bool:
    return abs(cents(difference)) <= tolerance


def status_label(
    difference: Decimal,
    tolerance: Decimal,
    *,
    known: Sequence[Decimal] = (),
) -> str:
    if within(difference, tolerance):
        return "abgeglichen"
    if any(cents(difference) == cents(amount) for amount in known):
        return "erklärt"
    if known:
        return "Differenz"
    return "offen"


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("reconciliation.yaml must be a mapping.")
    lists = raw.get("konten")
    if not isinstance(lists, dict):
        raise ValueError("reconciliation.yaml needs konten.")
    stichtag = raw.get("stichtag")
    parsed = date.fromisoformat(str(stichtag)) if stichtag else None
    checks = tuple(
        (str(item["id"]), str(item["name"]))
        for item in raw.get("pruefungen", ())
        if isinstance(item, dict)
    )
    expected = {f"P{index}" for index in range(1, 10)}
    if not expected <= {item[0] for item in checks}:
        raise ValueError("reconciliation.yaml must list P1 to P9.")
    zero_accounts = _account_list(lists, "pruefkonten", "P8")
    if zero_accounts.expected is None:
        raise ValueError("pruefkonten need an expected balance.")
    return Config(
        tolerance=parse_amount(raw.get("toleranz")),
        stichtag=parsed,
        receivables=_account_list(lists, "forderungen", "P6"),
        payables=_account_list(lists, "verbindlichkeiten", "P7"),
        inventory=_account_list(lists, "lager", "P8"),
        checks=checks,
        zero_accounts=zero_accounts,
        known=_known_differences(raw.get("bekannte_differenzen")),
    )


def load_mapping(path: Path) -> tuple[MappingRow, ...]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != MAPPING_COLUMNS:
            raise ValueError("kpi_mapping.csv has unexpected columns.")
        rows = [_mapping_row(raw) for raw in reader]
    seen: set[tuple[str, str]] = set()
    per_account: dict[str, list[MappingRow]] = defaultdict(list)
    for row in rows:
        key = (row.account, row.rule)
        if key in seen:
            raise ValueError(f"Duplicate mapping {row.account} {row.rule}.")
        seen.add(key)
        per_account[row.account].append(row)
    for account, group in per_account.items():
        if len(group) != 1:
            raise ValueError(f"Account {account} needs exactly one mapping row.")
    return tuple(rows)


def build_report(
    books: Books,
    mapping: Sequence[MappingRow],
    config: Config,
    as_of: date,
    generated_at: datetime,
) -> Report:
    _require_period(books.trial, ytd_opening(as_of))
    _require_period(books.trial, prior_month_end(as_of))
    _require_period(books.trial, as_of)
    for end in months_through(as_of):
        _require_calendar_month(books.trial, end)
    rows = _with_unmapped(mapping, books, as_of)
    p1 = _p1(books.gl)
    month_gl = _gl_sides(books.gl, prior_month_end(as_of), as_of)
    ytd_gl = _gl_sides(books.gl, ytd_opening(as_of), as_of)
    stock_gl = _gl_sides(books.gl, None, as_of)
    month_buckets_gl, month_buckets_tb = _buckets(
        rows, month_gl, books.trial, (as_of,), prior_month_end(as_of), as_of
    )
    ytd_buckets_gl, ytd_buckets_tb = _buckets(
        rows, ytd_gl, books.trial, months_through(as_of), ytd_opening(as_of), as_of
    )
    month_clearing = _receipt_clearing(books.item_values, prior_month_end(as_of), as_of)
    ytd_clearing = _receipt_clearing(books.item_values, ytd_opening(as_of), as_of)
    month_buckets_gl, month_buckets_tb = _apply_clearing(
        month_buckets_gl, month_buckets_tb, month_clearing
    )
    ytd_buckets_gl, ytd_buckets_tb = _apply_clearing(ytd_buckets_gl, ytd_buckets_tb, ytd_clearing)
    bridge_month = _bridge(
        month_buckets_gl,
        month_buckets_tb,
        rows,
        month_gl,
        books,
        prior_month_end(as_of),
        as_of,
    )
    bridge_ytd = _bridge(
        ytd_buckets_gl, ytd_buckets_tb, rows, ytd_gl, books, ytd_opening(as_of), as_of
    )
    names = _names(books, rows)
    accounts = _account_checks(books, names, month_gl, stock_gl, as_of)
    p6_signed = Figure(
        _open_amount(books.customers, as_of),
        _balance_sum(books.trial, config.receivables.numbers, as_of),
    )
    p7_signed = Figure(
        _open_amount(books.vendors, as_of),
        _balance_sum(books.trial, config.payables.numbers, as_of),
    )
    actual, posted = _inventory_values(books.item_values, as_of)
    p8 = Figure(actual, _balance_sum(books.trial, config.inventory.numbers, as_of))
    gaps = _inventory_gaps(books, as_of, set(config.inventory.numbers))
    known_p8 = tuple(item.amount for item in config.known if item.check_id == "P8")
    p8_status = status_label(p8.difference, config.tolerance, known=known_p8)
    p8_explained = p8_status in {"abgeglichen", "erklärt"}
    department, customer_group = _dimension_sets(books.dimensions)
    guv_entries = tuple(entry for entry in books.gl if _is_income(books, entry.account))
    kpi_unassigned = {
        bucket: _unassigned(
            books, rows, ytd_gl, bucket, department, customer_group, ytd_opening(as_of), as_of
        )
        for bucket in ("UMSATZ", "WARENEINSATZ", "BETRIEBSAUFWAND", "ABSCHREIBUNG")
    }
    after_protocol = tuple(entry for entry in books.gl if entry.posting_date > as_of)
    snapshot_cutoff = books.snapshot_cutoff or as_of
    after_snapshot = tuple(entry for entry in books.gl if entry.posting_date > snapshot_cutoff)
    return Report(
        as_of=as_of,
        generated_at=generated_at,
        company=books.company,
        environment=books.environment,
        stand=books.stand,
        snapshot_name=books.snapshot_name,
        tolerance=config.tolerance,
        receivables=config.receivables,
        payables=config.payables,
        inventory=config.inventory,
        p1=p1,
        p4_month=_bucket_figure(month_buckets_gl, month_buckets_tb, "UMSATZ"),
        p4_ytd=_bucket_figure(ytd_buckets_gl, ytd_buckets_tb, "UMSATZ"),
        p5_month=bridge_month.ebit,
        p5_ytd=bridge_ytd.ebit,
        p6=p6_signed,
        p7=Figure(cents(-p7_signed.report), cents(-p7_signed.reference)),
        p8=p8,
        p8_cost_gap=cents(actual - posted),
        bridge_month=bridge_month,
        bridge_ytd=bridge_ytd,
        values_month=_value_bridge(
            books.sales, rows, month_gl, prior_month_end(as_of), as_of, month_clearing
        ),
        values_ytd=_value_bridge(
            books.sales, rows, ytd_gl, ytd_opening(as_of), as_of, ytd_clearing
        ),
        accounts=accounts,
        counts=books.counts,
        after_protocol=len(after_protocol),
        after_protocol_from=_min_date(after_protocol),
        after_protocol_to=_max_date(after_protocol),
        after_snapshot=len(after_snapshot),
        after_snapshot_from=_min_date(after_snapshot),
        after_snapshot_to=_max_date(after_snapshot),
        guv_entries=len(guv_entries),
        with_department=sum(1 for entry in guv_entries if entry.dimension_set_id in department),
        with_customer_group=sum(
            1 for entry in guv_entries if entry.dimension_set_id in customer_group
        ),
        kpi_unassigned=kpi_unassigned,
        credit_5021_2025=_credit_in_year(books.gl, "5021", 2025),
        standard_credit=_standard_credit(books.gl),
        standard_lines=_standard_lines(books.gl),
        standard_date=_standard_date(books.gl),
        value_groups_2025=_value_groups(books.item_values, 2025),
        ledger_groups_2025=_ledger_groups(books.item_ledger, 2025),
        inventory_gaps=gaps,
        movement=_movement(books, rows),
        category_notes=_category_notes(books),
        p8_explained=p8_explained,
        zero_balances=_zero_balances(books, config.zero_accounts, as_of),
        variance_lines=_variance_lines(books, mapping, books.snapshot_cutoff or as_of),
        p5b=_p5b_rows(books, rows, as_of),
        p8_status=p8_status,
        p8_evidence=_p8_evidence(books, gaps)
        if not within(p8.difference, config.tolerance)
        else "",
        cogs_note=_cogs_credit_note(books, as_of),
        receipt_2025=_receipt_clearing(books.item_values, date(2024, 12, 31), date(2025, 12, 31)),
        revenue_cut_month=_account_figure(
            rows, month_gl, books.trial, "4201", prior_month_end(as_of), as_of
        ),
        revenue_cut_ytd=_account_figure(
            rows, ytd_gl, books.trial, "4201", ytd_opening(as_of), as_of
        ),
        known=config.known,
    )


def render_markdown(report: Report) -> str:
    lines = [
        f"# Abstimmprotokoll {plain(_month_name(report.as_of))}",
        "",
        "## Kopf",
        "",
        _table(
            ("Angabe", "Wert"),
            (
                ("Firma", plain(report.company)),
                ("Umgebung", plain(report.environment)),
                ("Stichtag", fmt_date(report.as_of)),
                ("Zeitpunkt", report.generated_at.strftime("%d.%m.%Y %H:%M")),
                ("Datenstand", f"{report.stand}, Snapshot {report.snapshot_name}"),
                ("Toleranz", f"{fmt_money(report.tolerance)} EUR"),
            ),
        ),
        "",
        "## Kennzahlen",
        "",
        _table(
            ("Prüfung", "Kennzahl", "Periode", "Sachposten", "Saldenliste", "Differenz", "Status"),
            (
                _kpi_row("P4", "Umsatz", "Monat", report.p4_month, report.tolerance),
                _kpi_row("P4", "Umsatz", "YTD", report.p4_ytd, report.tolerance),
                _kpi_row("P5", "EBIT", "Monat", report.p5_month, report.tolerance),
                _kpi_row("P5", "EBIT", "YTD", report.p5_ytd, report.tolerance),
                _kpi_row("P6", "Offene Forderungen", "Stichtag", report.p6, report.tolerance),
                _kpi_row("P7", "Verbindlichkeiten", "Stichtag", report.p7, report.tolerance),
                _kpi_row(
                    "P8",
                    "Bestandswert",
                    "Stichtag",
                    report.p8,
                    report.tolerance,
                    status=report.p8_status,
                ),
            ),
        ),
        "",
        _account_list_sentence(report),
        "",
        "Verbindlichkeiten stehen im Bericht positiv. Die Saldenliste führt sie im Haben, der "
        "Vergleich dreht das Vorzeichen auf beiden Seiten.",
        "",
        "Hinweis Lagerregulierung: costAmountActual minus costPostedToGL ist "
        f"{fmt_money(report.p8_cost_gap)}.",
        "",
        "## Überleitung Ergebnis",
        "",
        "EBIT ist Umsatz minus Wareneinsatz minus Betriebsaufwand minus Abschreibung plus "
        "sonstiger Ertrag und Aufwand. "
        "Lagerzugang, Zins, Steuer und nicht zugeordnete Konten stehen darunter. "
        "Die Summe muss dem vorzeichenrichtigen Ergebnis aller GuV-Konten entsprechen.",
        "",
        _bridge_table(report),
        "",
        "## Überleitung Wertposten",
        "",
        "Verkaufsbetrag und Einstandsbetrag kommen aus den Verkaufswertposten. "
        "Der Einstandsbetrag ist costAmountActual und negativ. "
        "P5b stellt den Wareneinsatz gegen minus costPostedToGL.",
        "",
        _value_table(report),
        "",
        *_p5b_section(report),
        "## Konten",
        "",
        "P2 ist die Bewegung im Monat, P3 der Saldo zum Stichtag. "
        "Die Saldenliste ist die Änderung der Endsalden beziehungsweise der Endsaldo. "
        "Summen- und Überschriftenkonten stehen hier nicht. Die Saldenliste zählt sie zusätzlich "
        "zu den Buchungskonten.",
        "",
        _table(
            (
                "Konto",
                "Name",
                "P2 Sachposten",
                "P2 Saldenliste",
                "P2 Differenz",
                "P3 Sachposten",
                "P3 Saldenliste",
                "P3 Differenz",
            ),
            tuple(_account_row(row) for row in _sorted_accounts(report.accounts)),
        ),
        "",
        "## Konten mit Bewegung",
        "",
        "Bis zum Stichtag des Snapshots. Die Zuordnung ist der Vorschlag aus Kontoname und "
        "Kategorie und wird fachlich geprüft. "
        "Konto 5021 hat eine Zeile. Die Zerlegung steht in der Überleitung.",
        "",
        _table(
            ("Konto", "Name", "Bucket", "Regel"),
            tuple((row.account, plain(row.name), row.bucket, row.rule) for row in report.movement),
        ),
        "",
        *_variance_section(report),
        "## Befunde und Ursachen",
        "",
        *_findings(report),
        "",
        "## Prüfweg",
        "",
        *_method(report),
        "",
    ]
    text = "\n".join(lines).rstrip() + "\n"
    assert_no_secrets(text, ())
    return text


def render_csv(report: Report) -> str:
    buffer: list[list[str]] = []
    buffer.append(
        [
            "abschnitt",
            "pruefung",
            "kennzahl",
            "konto",
            "name",
            "periode",
            "sachposten",
            "saldenliste",
            "differenz",
            "status",
            "bemerkung",
        ]
    )
    for row in (
        ("kennzahl", "P4", "Umsatz", "", "", "Monat", report.p4_month),
        ("kennzahl", "P4", "Umsatz", "", "", "YTD", report.p4_ytd),
        ("kennzahl", "P5", "EBIT", "", "", "Monat", report.p5_month),
        ("kennzahl", "P5", "EBIT", "", "", "YTD", report.p5_ytd),
        ("kennzahl", "P6", "Offene Forderungen", "", "", "Stichtag", report.p6),
        ("kennzahl", "P7", "Verbindlichkeiten", "", "", "Stichtag", report.p7),
        ("kennzahl", "P8", "Bestandswert", "", "", "Stichtag", report.p8),
    ):
        section, check_id, name, account, account_name, period, figure = row
        buffer.append(
            [
                str(section),
                str(check_id),
                str(name),
                str(account),
                str(account_name),
                str(period),
                _dot(figure.report),
                _dot(figure.reference),
                _dot(figure.difference),
                report.p8_status
                if check_id == "P8"
                else status_label(figure.difference, report.tolerance),
                "",
            ]
        )
    for label, figure in _bridge_figures(report.bridge_ytd):
        buffer.append(
            [
                "ueberleitung",
                "P5",
                label,
                "",
                "",
                "YTD",
                _dot(figure.report),
                _dot(figure.reference),
                _dot(figure.difference),
                status_label(figure.difference, report.tolerance),
                "",
            ]
        )
    cut = report.revenue_cut_ytd or Figure(Decimal(0), Decimal(0))
    buffer.append(
        [
            "ueberleitung",
            "P5",
            "davon Fehlbuchung Kundenzahlungen auf 4201",
            "4201",
            "",
            "YTD",
            _dot(cut.report),
            _dot(cut.reference),
            _dot(cut.difference),
            status_label(cut.difference, report.tolerance),
            "",
        ]
    )
    for check in report.p5b:
        show = check.label.endswith("YTD") or not within(check.difference, report.tolerance)
        if not show:
            continue
        buffer.append(
            [
                "p5b",
                "P5b",
                "Wareneinsatz",
                "",
                "",
                check.label,
                _dot(check.fibu),
                _dot(check.reference),
                _dot(check.difference),
                status_label(check.difference, report.tolerance),
                "",
            ]
        )
    for row in _sorted_accounts(report.accounts):
        buffer.append(
            [
                "konto",
                "P2",
                "",
                row.account,
                plain(row.name),
                "Monat",
                _dot(row.p2.report),
                _dot(row.p2.reference),
                _dot(row.p2.difference),
                status_label(row.p2.difference, report.tolerance),
                "",
            ]
        )
        buffer.append(
            [
                "konto",
                "P3",
                "",
                row.account,
                plain(row.name),
                "Stichtag",
                _dot(row.p3.report),
                _dot(row.p3.reference),
                _dot(row.p3.difference),
                status_label(row.p3.difference, report.tolerance),
                "",
            ]
        )
    for row in report.zero_balances:
        buffer.append(
            [
                "pruefkonto",
                "P8",
                "Erwarteter Saldo",
                row.account,
                plain(row.name),
                "Stichtag",
                _dot(row.gl_balance),
                _dot(row.trial_balance),
                _dot(row.difference),
                status_label(row.difference, report.tolerance),
                f"erwartet {_dot(row.expected)}",
            ]
        )
    for row in report.variance_lines:
        buffer.append(
            [
                "abweichung",
                "",
                "Abweichungskonto",
                row.account,
                plain(row.name),
                "Snapshot",
                _dot(row.debit),
                _dot(row.credit),
                _dot(cents(row.debit - row.credit)),
                "abgeglichen" if row.debit == 0 and row.credit == 0 else "offen",
                "Bewegung laut AP-01: keine",
            ]
        )
    for item in report.counts:
        buffer.append(
            [
                "zeilen",
                "P9",
                item.entity,
                "",
                item.route,
                "",
                str(item.snapshot_rows),
                str(item.manifest_rows),
                str(item.difference),
                status_label(Decimal(item.difference), Decimal(0)),
                "",
            ]
        )
    text_buffer = io.StringIO()
    writer = csv.writer(text_buffer, lineterminator="\n")
    writer.writerows(buffer)
    text = text_buffer.getvalue()
    assert_no_secrets(text, ())
    return text


def write_protocol(
    books: Books,
    mapping: Sequence[MappingRow],
    config: Config,
    as_of: date,
    generated_at: datetime,
    folder: Path,
) -> Report:
    report = build_report(books, mapping, config, as_of, generated_at)
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"Abstimmprotokoll_{as_of.strftime('%Y-%m')}"
    folder.joinpath(f"{stem}.md").write_text(render_markdown(report), encoding="utf-8")
    folder.joinpath(f"{stem}.csv").write_text(render_csv(report), encoding="utf-8")
    return report


def load_books(folder: Path) -> Books:
    import pandas as pd

    manifest = json.loads(folder.joinpath("manifest.json").read_text(encoding="utf-8"))
    frames = {
        (str(item["route"]), str(item["entity"])): pd.read_parquet(folder / str(item["parquet"]))
        for item in manifest["entities"]
    }

    def records(route: str, entity: str) -> list[dict[str, Any]]:
        return frames[(route, entity)].to_dict(orient="records")

    analytics = "microsoft/analytics/v1.0"
    income = {
        norm_key(row.get("entryNo")): row
        for row in records(analytics, "incomeStatementGeneralLedgerEntries")
    }
    balance = {
        norm_key(row.get("entryNo")): row
        for row in records(analytics, "balanceSheetGeneralLedgerEntries")
    }
    gl = tuple(_gl_entry(row, income, balance) for row in records("v2.0", "generalLedgerEntries"))
    gl = tuple(entry for entry in gl if entry.posting_date is not None)
    chart = _chart(
        records("v2.0", "accounts"),
        records(analytics, "generalLedgerAccounts"),
        records(analytics, "generalLedgerAccountCategories"),
    )
    trial = tuple(_trial_point(row) for row in records("v2.0", "trialBalances"))
    counts = tuple(
        CountRow(
            str(item["route"]),
            str(item["entity"]),
            len(frames[(str(item["route"]), str(item["entity"]))]),
            int(item["rows"]),
        )
        for item in manifest["entities"]
    )
    closing = frozenset(
        norm_key(row.get("entryNo"))
        for row in records(analytics, "closingGeneralLedgerEntries")
        if norm_key(row.get("entryNo"))
    )
    return Books(
        gl=gl,
        trial=trial,
        chart=chart,
        customers=tuple(
            _detail(row, "cleEntryNo", "dclePostingDate", "dcleAmountLCY")
            for row in records(analytics, "customerLedgerEntries")
        ),
        vendors=tuple(
            _detail(row, "vleEntryNo", "dvlePostingDate", "dvleAmountLCY")
            for row in records(analytics, "vendorLedgerEntries")
        ),
        item_values=tuple(_item_value(row) for row in records(analytics, "itemValueEntries")),
        item_ledger=tuple(_item_ledger(row) for row in records(analytics, "itemLedgerEntries")),
        purchases=tuple(_purchase(row) for row in records(analytics, "purchaseValueEntries")),
        sales=tuple(_sales(row) for row in records(analytics, "salesValueEntries")),
        items={
            item.number: item
            for item in (_item(row) for row in records("v2.0", "items"))
            if item.number
        },
        dimensions=tuple(_dimension(row) for row in records(analytics, "dynamicDimensions")),
        counts=counts,
        closing_entries=closing,
        company=str(manifest.get("company") or ""),
        environment=str(manifest.get("environment") or ""),
        stand=str(manifest.get("stand") or ""),
        snapshot_name=folder.name,
        snapshot_cutoff=date.fromisoformat(str(manifest["stichtag"])),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write the reconciliation protocol for a snapshot."
    )
    parser.add_argument(
        "--month",
        default=None,
        help="Reporting month YYYY-MM. Default: snapshot month and prior month.",
    )
    parser.add_argument("--snapshot", default=None, help="Snapshot folder. Default: latest.")
    args = parser.parse_args(argv)
    _configure_stdio()
    folder = Path(args.snapshot) if args.snapshot else latest_snapshot()
    if folder is None or not folder.joinpath("manifest.json").is_file():
        print("ERROR: No snapshot.", file=sys.stderr)
        return 1
    root = Path(__file__).resolve().parents[1]
    try:
        config = load_config(root / "config" / "reconciliation.yaml")
        mapping = load_mapping(root / "config" / "kpi_mapping.csv")
        books = load_books(folder)
        targets = _targets(args.month, books, config)
        generated_at = datetime.now().astimezone()
        out = root / "docs" / "abstimmung"
        reports = [
            write_protocol(books, mapping, config, target, generated_at, out) for target in targets
        ]
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    failed = False
    for report in reports:
        print(
            f"{report.as_of.isoformat()} "
            f"P1 {fmt_money(report.p1)} "
            f"P4 {fmt_money(report.p4_month.difference)} "
            f"P5 {fmt_money(report.p5_month.difference)} "
            f"P6 {fmt_money(report.p6.difference)} "
            f"P7 {fmt_money(report.p7.difference)} "
            f"P8 {fmt_money(report.p8.difference)} "
            f"P9 {sum(abs(item.difference) for item in report.counts)}"
        )
        if not _accepted(report):
            failed = True
    return 1 if failed else 0


def _accepted(report: Report) -> bool:
    figures = (
        report.p4_month,
        report.p4_ytd,
        report.p5_month,
        report.p5_ytd,
        report.p6,
        report.p7,
    )
    if not within(report.p1, report.tolerance):
        return False
    if any(not within(item.difference, report.tolerance) for item in figures):
        return False
    if any(
        not within(row.p2.difference, report.tolerance)
        or not within(row.p3.difference, report.tolerance)
        for row in report.accounts
    ):
        return False
    if not within(report.bridge_month.difference.report, report.tolerance):
        return False
    if not within(report.bridge_month.difference.reference, report.tolerance):
        return False
    if not within(report.bridge_ytd.difference.report, report.tolerance):
        return False
    if not within(report.bridge_ytd.difference.reference, report.tolerance):
        return False
    if any(item.difference != 0 for item in report.counts):
        return False
    if any(not _zero_ok(row, report.tolerance) for row in report.zero_balances):
        return False
    if any(not within(row.difference, report.tolerance) for row in report.p5b):
        return False
    return report.p8_explained


def _targets(month: str | None, books: Books, config: Config) -> tuple[date, ...]:
    if month:
        return (parse_month(month),)
    if config.stichtag is not None:
        return (config.stichtag,)
    if books.snapshot_cutoff is None:
        raise ValueError("Snapshot has no stichtag.")
    current = books.snapshot_cutoff
    return (current, prior_month_end(current))


def _account_list(raw: Mapping[str, Any], key: str, check_id: str) -> AccountList:
    block = raw.get(key)
    if not isinstance(block, dict):
        raise ValueError(f"Missing account list {key}.")
    numbers = tuple(str(item).strip() for item in block.get("nummern", ()))
    status = str(block.get("status") or "").strip()
    if status not in {"vorläufig", "verifiziert"}:
        raise ValueError(f"{key} status must be vorläufig or verifiziert.")
    if not numbers or str(block.get("pruefung")) != check_id:
        raise ValueError(f"{key} does not match {check_id}.")
    expected_raw = block.get("erwartet")
    expected = None if expected_raw in (None, "") else parse_amount(expected_raw)
    return AccountList(
        check_id,
        numbers,
        str(block.get("quelle") or ""),
        status,
        str(block.get("hinweis") or ""),
        expected,
    )


def _known_differences(raw: Any) -> tuple[KnownDifference, ...]:
    if raw in (None, ""):
        return ()
    if not isinstance(raw, list):
        raise ValueError("bekannte_differenzen must be a list.")
    rows: list[KnownDifference] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("bekannte_differenzen entries must be mappings.")
        status = str(item.get("status") or "").strip()
        if status != "erklaert":
            raise ValueError("bekannte_differenzen status must be erklaert.")
        rows.append(
            KnownDifference(
                str(item.get("pruefung") or "").strip(),
                parse_amount(item.get("betrag")),
                plain(str(item.get("beleg") or "")),
                plain(str(item.get("artikel") or "")),
                plain(str(item.get("ursache") or "")),
                plain(str(item.get("quelle") or "")),
                status,
            )
        )
    return tuple(rows)


def _mapping_row(raw: Mapping[str, str]) -> MappingRow:
    bucket = raw["bucket"].strip()
    rule = raw["regel"].strip()
    if bucket not in BUCKETS or rule not in RULES:
        raise ValueError(f"Invalid mapping for {raw.get('konto')}.")
    sign = int(raw["vorzeichen"])
    if sign not in {-1, 1}:
        raise ValueError(f"Invalid sign for {raw.get('konto')}.")
    return MappingRow(
        account=raw["konto"].strip(),
        name=raw["kontoname"].strip(),
        bucket=bucket,
        rule=rule,
        sign=sign,
        source=raw["quelle"].strip(),
        note=raw["bemerkung"].strip(),
    )


def _with_unmapped(
    mapping: Sequence[MappingRow],
    books: Books,
    as_of: date,
) -> tuple[MappingRow, ...]:
    known = {row.account for row in mapping}
    extra: list[MappingRow] = []
    for entry in books.gl:
        if entry.posting_date > as_of or entry.account in known:
            continue
        if entry.debit == 0 and entry.credit == 0:
            continue
        if not _is_income(books, entry.account):
            continue
        known.add(entry.account)
        name = books.chart[entry.account].name if entry.account in books.chart else entry.account
        extra.append(
            MappingRow(
                entry.account, name, "NICHT_ZUGEORDNET", "NETTO", -1, "Bewegung ohne Zeile", ""
            )
        )
    return tuple(mapping) + tuple(extra)


def _p1(entries: Sequence[GlEntry]) -> Decimal:
    debit = sum((entry.debit for entry in entries), Decimal(0))
    credit = sum((entry.credit for entry in entries), Decimal(0))
    return cents(debit - credit)


def _gl_sides(
    entries: Sequence[GlEntry],
    start_after: date | None,
    end: date,
) -> dict[str, tuple[Decimal, Decimal]]:
    totals: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
    for entry in entries:
        if entry.posting_date > end:
            continue
        if start_after is not None and entry.posting_date <= start_after:
            continue
        slot = totals[entry.account]
        slot[0] += entry.debit
        slot[1] += entry.credit
    return {account: (pair[0], pair[1]) for account, pair in totals.items()}


def _buckets(
    mapping: Sequence[MappingRow],
    gl_sides: Mapping[str, tuple[Decimal, Decimal]],
    trial: Sequence[TrialPoint],
    months: Sequence[date],
    opening: date,
    closing: date,
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    gl_out: dict[str, Decimal] = defaultdict(Decimal)
    tb_out: dict[str, Decimal] = defaultdict(Decimal)
    for row in mapping:
        debit, credit = gl_sides.get(row.account, (Decimal(0), Decimal(0)))
        gl_out[row.bucket] += cents(row.sign * _basis(debit, credit, row.rule))
        if row.rule == "NETTO":
            net = _balance(trial, row.account, closing) - _balance(trial, row.account, opening)
            tb_basis = net
        else:
            turnover_debit, turnover_credit = _turnover(trial, row.account, months)
            tb_basis = _basis(turnover_debit, turnover_credit, row.rule)
        tb_out[row.bucket] += cents(row.sign * tb_basis)
    return dict(gl_out), dict(tb_out)


RECEIPT_TYPES = frozenset({"positive adjmt.", "output"})


def _receipt_clearing(
    rows: Sequence[CostLine],
    start_after: date | None,
    end: date,
) -> Decimal:
    """Positive credit amount: cost posted to GL for receipts without a purchase invoice."""
    total = Decimal(0)
    for row in rows:
        if row.posting_date > end:
            continue
        if start_after is not None and row.posting_date <= start_after:
            continue
        if row.item_ledger_type.casefold() not in RECEIPT_TYPES:
            continue
        total += row.cost_posted
    return cents(total)


def _apply_clearing(
    gl_buckets: Mapping[str, Decimal],
    tb_buckets: Mapping[str, Decimal],
    clearing: Decimal,
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    """WARENEINSATZ = net minus the credit-signed clearing. The report shows the credit positive."""
    gl = dict(gl_buckets)
    tb = dict(tb_buckets)
    gl["WARENEINSATZ"] = cents(gl.get("WARENEINSATZ", Decimal(0)) + clearing)
    tb["WARENEINSATZ"] = cents(tb.get("WARENEINSATZ", Decimal(0)) + clearing)
    gl["LAGERZUGANG_VERRECHNUNG"] = cents(gl.get("LAGERZUGANG_VERRECHNUNG", Decimal(0)) + clearing)
    tb["LAGERZUGANG_VERRECHNUNG"] = cents(tb.get("LAGERZUGANG_VERRECHNUNG", Decimal(0)) + clearing)
    return gl, tb


def _account_figure(
    mapping: Sequence[MappingRow],
    gl_sides: Mapping[str, tuple[Decimal, Decimal]],
    trial: Sequence[TrialPoint],
    account: str,
    opening: date,
    closing: date,
) -> Figure:
    gl_amount = Decimal(0)
    tb_amount = Decimal(0)
    for row in mapping:
        if row.account != account:
            continue
        debit, credit = gl_sides.get(row.account, (Decimal(0), Decimal(0)))
        gl_amount += cents(row.sign * _basis(debit, credit, row.rule))
        if row.rule == "NETTO":
            net = _balance(trial, row.account, closing) - _balance(trial, row.account, opening)
            tb_amount += cents(row.sign * net)
    return Figure(cents(gl_amount), cents(tb_amount))


def _fibu_cogs(
    books: Books,
    mapping: Sequence[MappingRow],
    start_after: date | None,
    end: date,
) -> Decimal:
    gl_sides = _gl_sides(books.gl, start_after, end)
    total = Decimal(0)
    for row in mapping:
        if row.bucket != "WARENEINSATZ":
            continue
        debit, credit = gl_sides.get(row.account, (Decimal(0), Decimal(0)))
        total += cents(row.sign * _basis(debit, credit, row.rule))
    return cents(total + _receipt_clearing(books.item_values, start_after, end))


def _sales_posted(sales: Sequence[SalesLine], start_after: date | None, end: date) -> Decimal:
    total = Decimal(0)
    for row in sales:
        if row.posting_date > end:
            continue
        if start_after is not None and row.posting_date <= start_after:
            continue
        total += row.cost_posted
    return cents(-total)


def _p5b_rows(books: Books, mapping: Sequence[MappingRow], as_of: date) -> tuple[CostCheck, ...]:
    years = [2025] if as_of.year >= 2025 else []
    if as_of.year != 2025:
        years.append(as_of.year)
    checks: list[CostCheck] = []
    for year in years:
        last_month = 12 if year < as_of.year else as_of.month
        for month in range(1, last_month + 1):
            end = month_end(year, month)
            start = prior_month_end(end)
            checks.append(
                CostCheck(
                    f"{year}-{month:02d}",
                    _fibu_cogs(books, mapping, start, end),
                    _sales_posted(books.sales, start, end),
                )
            )
        ytd_end = date(year, 12, 31) if year < as_of.year else as_of
        checks.append(
            CostCheck(
                f"{year} YTD",
                _fibu_cogs(books, mapping, date(year - 1, 12, 31), ytd_end),
                _sales_posted(books.sales, date(year - 1, 12, 31), ytd_end),
            )
        )
    return tuple(checks)


def _basis(debit: Decimal, credit: Decimal, rule: str) -> Decimal:
    if rule == "NETTO":
        return debit - credit
    if rule == "NUR_SOLL":
        return debit
    if rule == "NUR_HABEN":
        return credit
    raise ValueError(rule)


def _bridge(
    gl_buckets: Mapping[str, Decimal],
    tb_buckets: Mapping[str, Decimal],
    mapping: Sequence[MappingRow],
    gl_sides: Mapping[str, tuple[Decimal, Decimal]],
    books: Books,
    opening: date,
    closing: date,
) -> Bridge:
    buckets = {
        bucket: Figure(gl_buckets.get(bucket, Decimal(0)), tb_buckets.get(bucket, Decimal(0)))
        for bucket in BUCKETS
    }
    ebit = Figure(_ebit(gl_buckets), _ebit(tb_buckets))
    total = Figure(_bridge_sum(gl_buckets), _bridge_sum(tb_buckets))
    accounts = {row.account for row in mapping}
    gl_result = Decimal(0)
    tb_result = Decimal(0)
    for account in accounts:
        debit, credit = gl_sides.get(account, (Decimal(0), Decimal(0)))
        gl_result += -(debit - credit)
        tb_result += -(
            _balance(books.trial, account, closing) - _balance(books.trial, account, opening)
        )
    return Bridge(buckets, ebit, total, Figure(cents(gl_result), cents(tb_result)))


def _ebit(buckets: Mapping[str, Decimal]) -> Decimal:
    total = Decimal(0)
    for bucket, amount in buckets.items():
        if bucket in EBIT_PLUS:
            total += amount
        elif bucket in EBIT_MINUS:
            total -= amount
    return cents(total)


def _bridge_sum(buckets: Mapping[str, Decimal]) -> Decimal:
    total = _ebit(buckets)
    for bucket in BRIDGE_EXTRA:
        total += buckets.get(bucket, Decimal(0))
    return cents(total)


def _bucket_figure(
    gl_buckets: Mapping[str, Decimal],
    tb_buckets: Mapping[str, Decimal],
    bucket: str,
) -> Figure:
    return Figure(gl_buckets.get(bucket, Decimal(0)), tb_buckets.get(bucket, Decimal(0)))


def _account_checks(
    books: Books,
    names: Mapping[str, str],
    month_gl: Mapping[str, tuple[Decimal, Decimal]],
    stock_gl: Mapping[str, tuple[Decimal, Decimal]],
    as_of: date,
) -> tuple[AccountCheck, ...]:
    opening = prior_month_end(as_of)
    accounts = _posting_accounts(books)
    rows: list[AccountCheck] = []
    for account in accounts:
        gl_debit, gl_credit = month_gl.get(account, (Decimal(0), Decimal(0)))
        stock_debit, stock_credit = stock_gl.get(account, (Decimal(0), Decimal(0)))
        p2 = Figure(
            cents(gl_debit - gl_credit),
            cents(_balance(books.trial, account, as_of) - _balance(books.trial, account, opening)),
        )
        p3 = Figure(cents(stock_debit - stock_credit), cents(_balance(books.trial, account, as_of)))
        rows.append(AccountCheck(account, names.get(account, account), p2, p3))
    return tuple(rows)


def _posting_accounts(books: Books) -> tuple[str, ...]:
    found: set[str] = set()
    for point in books.trial:
        if is_posting_type(readable_token(point.account_type)):
            found.add(point.account)
    for entry in books.gl:
        chart = books.chart.get(entry.account)
        if chart is None or is_posting_type(chart.account_type):
            found.add(entry.account)
    return tuple(sorted(found, key=lambda number: (len(number), number)))


def _names(books: Books, mapping: Sequence[MappingRow]) -> dict[str, str]:
    names = {row.account: row.name for row in mapping}
    for number, account in books.chart.items():
        names.setdefault(number, account.name)
    for point in books.trial:
        names.setdefault(point.account, point.name)
    return names


def _open_amount(details: Sequence[Detail], as_of: date) -> Decimal:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in details:
        if row.posting_date <= as_of:
            totals[row.entry_no] += row.amount
    return sum(
        (cents(amount) for amount in totals.values() if abs(cents(amount)) >= OPEN_THRESHOLD),
        Decimal(0),
    )


def _balance_sum(trial: Sequence[TrialPoint], accounts: Sequence[str], as_of: date) -> Decimal:
    return cents(sum((_balance(trial, account, as_of) for account in accounts), Decimal(0)))


def _balance(trial: Sequence[TrialPoint], account: str, day: date) -> Decimal:
    for point in trial:
        if point.account == account and point.end == day:
            return point.balance
    return Decimal(0)


def _zero_ok(row: BalanceCheck, tolerance: Decimal) -> bool:
    return within(row.difference, tolerance) and within(
        cents(row.gl_balance - row.expected), tolerance
    )


def _zero_balances(
    books: Books, accounts: AccountList | None, as_of: date
) -> tuple[BalanceCheck, ...]:
    if accounts is None or accounts.expected is None:
        return ()
    rows: list[BalanceCheck] = []
    for number in accounts.numbers:
        gl_balance = Decimal(0)
        for entry in books.gl:
            if entry.account == number and entry.posting_date <= as_of:
                gl_balance += entry.amount
        name = books.chart[number].name if number in books.chart else number
        rows.append(
            BalanceCheck(
                number,
                name,
                cents(gl_balance),
                _balance(books.trial, number, as_of),
                accounts.expected,
            )
        )
    return tuple(rows)


def _variance_lines(
    books: Books, mapping: Sequence[MappingRow], cutoff: date
) -> tuple[VarianceLine, ...]:
    chosen = [row for row in mapping if "Abweichungskonto" in row.note]
    lines: list[VarianceLine] = []
    seen: set[str] = set()
    for row in chosen:
        if row.account in seen:
            continue
        seen.add(row.account)
        debit = Decimal(0)
        credit = Decimal(0)
        for entry in books.gl:
            if entry.account == row.account and entry.posting_date <= cutoff:
                debit += entry.debit
                credit += entry.credit
        lines.append(VarianceLine(row.account, row.name, cents(debit), cents(credit)))
    return tuple(sorted(lines, key=lambda item: (len(item.account), item.account)))


def _turnover(
    trial: Sequence[TrialPoint],
    account: str,
    months: Sequence[date],
) -> tuple[Decimal, Decimal]:
    debit = Decimal(0)
    credit = Decimal(0)
    for end in months:
        for point in trial:
            if (
                point.account == account
                and point.end == end
                and is_calendar_month(point.start, point.end)
            ):
                debit += point.debit
                credit += point.credit
                break
    return debit, credit


def _require_period(trial: Sequence[TrialPoint], day: date) -> None:
    if not any(point.end == day for point in trial):
        raise ValueError(f"Trial balance has no rows for {day.isoformat()}.")


def _require_calendar_month(trial: Sequence[TrialPoint], day: date) -> None:
    if not any(point.end == day and is_calendar_month(point.start, point.end) for point in trial):
        raise ValueError(f"Trial balance has no calendar month {day.isoformat()}.")


def _inventory_values(rows: Sequence[CostLine], as_of: date) -> tuple[Decimal, Decimal]:
    actual = Decimal(0)
    posted = Decimal(0)
    for row in rows:
        if row.posting_date <= as_of:
            actual += row.cost_actual
            posted += row.cost_posted
    return cents(actual), cents(posted)


def _inventory_gaps(books: Books, as_of: date, accounts: set[str]) -> tuple[DocumentGap, ...]:
    gl_amounts: dict[str, Decimal] = defaultdict(Decimal)
    gl_dates: dict[str, date] = {}
    for entry in books.gl:
        if entry.account not in accounts or entry.posting_date > as_of or not entry.document_number:
            continue
        gl_amounts[entry.document_number] += entry.amount
        current = gl_dates.get(entry.document_number)
        if current is None or entry.posting_date < current:
            gl_dates[entry.document_number] = entry.posting_date
    ledger_amounts: dict[str, Decimal] = defaultdict(Decimal)
    meta: dict[str, CostLine] = {}
    for row in books.item_ledger:
        if row.posting_date > as_of or not row.document_number:
            continue
        ledger_amounts[row.document_number] += row.cost_actual
        meta.setdefault(row.document_number, row)
    for row in books.purchases:
        if row.document_number:
            meta.setdefault(row.document_number, row)
    gaps: list[DocumentGap] = []
    for document in sorted(set(gl_amounts) | set(ledger_amounts)):
        difference = cents(gl_amounts[document] - ledger_amounts[document])
        if difference == 0:
            continue
        sample = meta.get(document)
        gaps.append(
            DocumentGap(
                document=document,
                posting_date=gl_dates.get(document) or (sample.posting_date if sample else as_of),
                gl_amount=cents(gl_amounts[document]),
                ledger_amount=cents(ledger_amounts[document]),
                item_no=sample.item_no if sample else "",
                entry_type=sample.entry_type if sample else "",
                item_ledger_type=sample.item_ledger_type if sample else "",
            )
        )
    return tuple(gaps)


def _value_bridge(
    sales: Sequence[SalesLine],
    mapping: Sequence[MappingRow],
    gl_sides: Mapping[str, tuple[Decimal, Decimal]],
    start_after: date,
    end: date,
    clearing: Decimal = Decimal(0),
) -> ValueBridge:
    sales_amount = Decimal(0)
    sales_cost = Decimal(0)
    for row in sales:
        if start_after < row.posting_date <= end:
            sales_amount += row.sales_amount
            sales_cost += row.cost_actual
    revenue = Decimal(0)
    cogs = Decimal(0)
    account_4201 = Decimal(0)
    for row in mapping:
        debit, credit = gl_sides.get(row.account, (Decimal(0), Decimal(0)))
        amount = cents(row.sign * _basis(debit, credit, row.rule))
        if row.bucket == "UMSATZ":
            revenue += amount
        if row.bucket == "WARENEINSATZ":
            cogs += amount
        if row.account == "4201" and row.rule == "NETTO":
            account_4201 += debit - credit
    return ValueBridge(
        cents(sales_amount),
        cents(sales_cost),
        cents(revenue),
        cents(cogs + clearing),
        cents(account_4201),
    )


def _dimension_sets(rows: Sequence[DimensionLine]) -> tuple[set[str], set[str]]:
    department: set[str] = set()
    customer_group: set[str] = set()
    for row in rows:
        code = row.code.casefold()
        if code == "abteilung":
            department.add(row.set_id)
        elif code == "debitorengruppe":
            customer_group.add(row.set_id)
    return department, customer_group


def _unassigned(
    books: Books,
    mapping: Sequence[MappingRow],
    gl_sides: Mapping[str, tuple[Decimal, Decimal]],
    bucket: str,
    department: set[str],
    customer_group: set[str],
    start_after: date,
    end: date,
) -> tuple[int, int, Decimal, Decimal]:
    rules = {row.account: row for row in mapping if row.bucket == bucket}
    entries = [
        entry
        for entry in books.gl
        if (
            entry.account in rules
            and start_after < entry.posting_date <= end
            and _counts_for(entry, rules[entry.account])
        )
    ]
    count = len(entries)
    amount = sum((abs(entry.amount) for entry in entries), Decimal(0))
    missing_department = [entry for entry in entries if entry.dimension_set_id not in department]
    missing_amount = sum((abs(entry.amount) for entry in missing_department), Decimal(0))
    return count, len(missing_department), cents(amount), cents(missing_amount)


def _counts_for(entry: GlEntry, row: MappingRow) -> bool:
    if row.rule == "NUR_SOLL":
        return entry.debit != 0
    if row.rule == "NUR_HABEN":
        return entry.credit != 0
    return entry.debit != 0 or entry.credit != 0


def _is_income(books: Books, account: str) -> bool:
    chart = books.chart.get(account)
    return bool(chart and chart.income_statement)


def _movement(books: Books, mapping: Sequence[MappingRow]) -> tuple[MovementAccount, ...]:
    cutoff = books.snapshot_cutoff
    active: set[str] = set()
    for entry in books.gl:
        if cutoff is not None and entry.posting_date > cutoff:
            continue
        if entry.debit != 0 or entry.credit != 0:
            active.add(entry.account)
    rows = [
        MovementAccount(row.account, row.name, row.bucket, row.rule)
        for row in mapping
        if row.account in active
    ]
    return tuple(sorted(rows, key=lambda row: (len(row.account), row.account, row.bucket)))


def _category_notes(books: Books) -> tuple[str, ...]:
    notes: list[str] = []
    stock = books.chart.get("1102")
    raw = books.chart.get("1001")
    if stock is not None:
        place = plain(stock.hierarchy) or "ohne Knoten"
        notes.append(
            f"1102 {plain(stock.name)} steht in der Hierarchie unter {place}. "
            "Die Kategorie Lagerbestand ist das nicht."
        )
    if raw is not None:
        notes.append(f"1001 {plain(raw.name)} steht unter {plain(raw.hierarchy) or 'ohne Knoten'}.")
    for number in ("0210", "0280", "1085", "2720", "4091", "60410"):
        account = books.chart.get(number)
        if account is None:
            continue
        if account.subcategory or account.subcategory_entry:
            continue
        notes.append(
            f"{number} {plain(account.name)} hat die v2-Kategorie {account.category or 'leer'} "
            f"und keine Unterkategorie (Hierarchieeintrag {account.subcategory_entry})."
        )
    return tuple(notes)


def _credit_in_year(entries: Sequence[GlEntry], account: str, year: int) -> Decimal:
    return cents(
        sum(
            (
                entry.credit
                for entry in entries
                if entry.account == account and entry.posting_date.year == year
            ),
            Decimal(0),
        )
    )


def _standard_credit(entries: Sequence[GlEntry]) -> Decimal:
    return cents(
        sum(
            (
                entry.credit
                for entry in entries
                if entry.account == "5021" and entry.document_number == "STANDARD"
            ),
            Decimal(0),
        )
    )


def _standard_lines(entries: Sequence[GlEntry]) -> int:
    return sum(
        1
        for entry in entries
        if entry.account == "5021" and entry.document_number == "STANDARD" and entry.credit != 0
    )


def _standard_date(entries: Sequence[GlEntry]) -> date | None:
    dates = [
        entry.posting_date
        for entry in entries
        if entry.account == "5021" and entry.document_number == "STANDARD" and entry.credit != 0
    ]
    return min(dates) if dates else None


def _value_groups(
    rows: Sequence[CostLine],
    year: int,
) -> tuple[tuple[str, str, int, Decimal, Decimal], ...]:
    grouped: dict[tuple[str, str], list[Decimal]] = defaultdict(
        lambda: [Decimal(0), Decimal(0), Decimal(0)]
    )
    for row in rows:
        if row.posting_date.year != year:
            continue
        slot = grouped[(row.item_ledger_type or "(leer)", row.document_type or "(leer)")]
        slot[0] += 1
        slot[1] += row.cost_actual
        slot[2] += row.cost_posted
    return tuple(
        (key[0], key[1], int(value[0]), cents(value[1]), cents(value[2]))
        for key, value in sorted(grouped.items())
    )


def _ledger_groups(
    rows: Sequence[CostLine],
    year: int,
) -> tuple[tuple[str, str, int, Decimal], ...]:
    grouped: dict[tuple[str, str], list[Decimal]] = defaultdict(lambda: [Decimal(0), Decimal(0)])
    for row in rows:
        if row.posting_date.year != year:
            continue
        slot = grouped[(row.entry_type or "(leer)", row.document_number or "(leer)")]
        slot[0] += 1
        slot[1] += row.cost_actual
    return tuple(
        (key[0], key[1], int(value[0]), cents(value[1]))
        for key, value in sorted(grouped.items())
        if value[1] != 0
    )


def _min_date(entries: Sequence[GlEntry]) -> date | None:
    if not entries:
        return None
    return min(entry.posting_date for entry in entries)


def _max_date(entries: Sequence[GlEntry]) -> date | None:
    if not entries:
        return None
    return max(entry.posting_date for entry in entries)


def _gl_entry(
    row: Mapping[str, Any],
    income: Mapping[str, Mapping[str, Any]],
    balance: Mapping[str, Mapping[str, Any]],
) -> GlEntry:
    entry_no = norm_key(row.get("entryNumber"))
    posted = parse_iso_date(row.get("postingDate"))
    analytics = income.get(entry_no) or balance.get(entry_no) or {}
    return GlEntry(
        entry_no=entry_no,
        account=norm_key(row.get("accountNumber")),
        posting_date=posted or date.min,
        debit=parse_amount(row.get("debitAmount")),
        credit=parse_amount(row.get("creditAmount")),
        dimension_set_id=norm_key(analytics.get("dimensionSetID")),
        source_code=plain(str(analytics.get("sourceCode") or "")),
        source_type=plain(readable_token(analytics.get("sourceType"))),
        description=plain(str(analytics.get("description") or "")),
        document_number=plain(str(row.get("documentNumber") or "")),
        document_type=plain(readable_token(row.get("documentType"))),
    )


def _chart(
    accounts: Sequence[Mapping[str, Any]],
    gl_accounts: Sequence[Mapping[str, Any]],
    categories: Sequence[Mapping[str, Any]],
) -> dict[str, ChartAccount]:
    tree = {int(row["entryNo"]): row for row in categories}
    analytics = {norm_key(row.get("accountNo")): row for row in gl_accounts}
    chart: dict[str, ChartAccount] = {}
    for row in accounts:
        number = norm_key(row.get("number"))
        meta = analytics.get(number, {})
        sub_no = int(meta.get("accountSubcategoryEntryNo") or 0)
        node = tree.get(sub_no, {})
        parent = tree.get(int(node.get("parentEntryNo") or 0), {}) if node else {}
        income = readable_token(meta.get("incomeBalance")).casefold() == "income statement"
        chart[number] = ChartAccount(
            number=number,
            name=plain(str(row.get("displayName") or meta.get("accountName") or "")),
            account_type=readable_token(row.get("accountType")),
            income_statement=income,
            category=readable_token(row.get("category")),
            subcategory=readable_token(row.get("subCategory")),
            hierarchy=readable_token(node.get("description")) if node else "",
            parent=readable_token(parent.get("description")) if parent else "",
            subcategory_entry=sub_no,
        )
    return chart


def _trial_point(row: Mapping[str, Any]) -> TrialPoint:
    start = parse_iso_date(row.get("periodStart")) or date.min
    end = parse_iso_date(row.get("periodEnd")) or date.min
    return TrialPoint(
        account=norm_key(row.get("number")),
        name=plain(str(row.get("display") or "")),
        account_type=str(row.get("accountType") or ""),
        start=start,
        end=end,
        debit=parse_amount(row.get("totalDebit")),
        credit=parse_amount(row.get("totalCredit")),
        balance=parse_amount(row.get("balanceAtDateDebit"))
        - parse_amount(row.get("balanceAtDateCredit")),
    )


def _detail(row: Mapping[str, Any], entry_field: str, date_field: str, amount_field: str) -> Detail:
    posted = parse_iso_date(row.get(date_field)) or date.max
    return Detail(norm_key(row.get(entry_field)), posted, parse_amount(row.get(amount_field)))


def _item_value(row: Mapping[str, Any]) -> CostLine:
    return CostLine(
        posting_date=parse_iso_date(row.get("postingDate")) or date.min,
        cost_actual=parse_amount(row.get("costAmountActual")),
        cost_posted=parse_amount(row.get("costPostedToGL")),
        item_ledger_type=plain(str(row.get("itemLedgerEntryType") or "")),
        document_type=plain(readable_token(row.get("documentType"))),
        item_no=plain(str(row.get("itemNo") or "")),
        entry_no=norm_key(row.get("entryNo")),
    )


def _item_ledger(row: Mapping[str, Any]) -> CostLine:
    return CostLine(
        posting_date=parse_iso_date(row.get("postingDate")) or date.min,
        cost_actual=parse_amount(row.get("costAmountActual")),
        entry_type=plain(str(row.get("entryType") or "")),
        document_number=plain(str(row.get("documentNo") or "")),
        document_type=plain(readable_token(row.get("documentType"))),
        item_no=plain(str(row.get("itemNo") or "")),
        item_ledger_type=plain(str(row.get("entryType") or "")),
        entry_no=norm_key(row.get("entryNo")),
        quantity=parse_amount(row.get("quantity")),
    )


def _purchase(row: Mapping[str, Any]) -> CostLine:
    return CostLine(
        posting_date=parse_iso_date(row.get("postingDate")) or date.min,
        cost_actual=parse_amount(row.get("costAmountActual")),
        document_number=plain(str(row.get("documentNo") or "")),
        document_type=plain(readable_token(row.get("documentType"))),
        entry_type=plain(str(row.get("entryType") or "")),
        item_ledger_type=plain(str(row.get("itemLedgerEntryType") or "")),
        item_no=plain(str(row.get("itemNo") or "")),
        entry_no=norm_key(row.get("entryNo")),
        ledger_entry_no=norm_key(row.get("itemLedgerEntryNo")),
    )


def _sales(row: Mapping[str, Any]) -> SalesLine:
    return SalesLine(
        posting_date=parse_iso_date(row.get("postingDate")) or date.min,
        sales_amount=parse_amount(row.get("salesAmountActual")),
        cost_actual=parse_amount(row.get("costAmountActual")),
        cost_posted=parse_amount(row.get("costPostedToGL")),
    )


def _item(row: Mapping[str, Any]) -> ItemRecord:
    return ItemRecord(
        number=plain(str(row.get("number") or "")),
        name=plain(str(row.get("displayName") or "")),
        item_type=plain(readable_token(row.get("type"))),
        product_group=plain(str(row.get("generalProductPostingGroupCode") or "")),
        inventory_group=plain(str(row.get("inventoryPostingGroupCode") or "")),
    )


def _dimension(row: Mapping[str, Any]) -> DimensionLine:
    return DimensionLine(
        norm_key(row.get("dimensionSetID")),
        plain(str(row.get("customDimensionCode") or "")),
    )


def _table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    head = "| " + " | ".join(plain(item) for item in headers) + " |"
    rule = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(plain(item) for item in row) + " |" for row in rows]
    return "\n".join([head, rule, *body])


def _kpi_row(
    check_id: str,
    name: str,
    period: str,
    figure: Figure,
    tolerance: Decimal,
    *,
    status: str | None = None,
) -> tuple[str, ...]:
    label = status if status else status_label(figure.difference, tolerance)
    return (
        check_id,
        name,
        period,
        fmt_money(figure.report),
        fmt_money(figure.reference),
        fmt_money(figure.difference),
        label,
    )


def _account_row(row: AccountCheck) -> tuple[str, ...]:
    return (
        row.account,
        plain(row.name),
        fmt_money(row.p2.report),
        fmt_money(row.p2.reference),
        fmt_money(row.p2.difference),
        fmt_money(row.p3.report),
        fmt_money(row.p3.reference),
        fmt_money(row.p3.difference),
    )


def _sorted_accounts(rows: Sequence[AccountCheck]) -> tuple[AccountCheck, ...]:
    def rank(row: AccountCheck) -> tuple[int, Decimal, int, str]:
        diff = max(abs(row.p2.difference), abs(row.p3.difference))
        return (0 if diff != 0 else 1, -diff, len(row.account), row.account)

    return tuple(sorted(rows, key=rank))


def _variance_section(report: Report) -> list[str]:
    if not report.variance_lines:
        return []
    numbers = ", ".join(row.account for row in report.variance_lines)
    quiet = all(row.debit == 0 and row.credit == 0 for row in report.variance_lines)
    snapshot = (
        "Im Snapshot bis zum Stichtag ebenfalls keine Bewegung."
        if quiet
        else "Im Snapshot gibt es Bewegung, die Beträge stehen in der Tabelle."
    )
    return [
        "## Abweichungskonten",
        "",
        f"Konten {numbers}. Bucket WARENEINSATZ. Bewegung laut AP-01: keine. {snapshot}",
        "",
        _table(
            ("Konto", "Name", "Soll", "Haben"),
            tuple(
                (row.account, plain(row.name), fmt_money(row.debit), fmt_money(row.credit))
                for row in report.variance_lines
            ),
        ),
        "",
    ]


def _source_status(item: AccountList) -> str:
    if item.status == "verifiziert" and item.source == "BC-Einrichtung":
        return "verifiziert (BC-Einrichtung)"
    return f"Quelle {item.source}, Status {item.status}"


def _account_list_sentence(report: Report) -> str:
    parts = (
        ("Forderungskonten", report.receivables),
        ("Verbindlichkeitskonten", report.payables),
        ("Lagerkonten", report.inventory),
    )
    rendered = []
    for label, item in parts:
        numbers = ", ".join(item.numbers)
        rendered.append(
            f"{label} {numbers}. Quelle und Status: {_source_status(item)}. {plain(item.note)}"
        )
    for row in report.zero_balances:
        rendered.append(
            f"Prüfkonto {row.account} {plain(row.name)}. "
            f"Sachposten {fmt_money(row.gl_balance)}, "
            f"Saldenliste {fmt_money(row.trial_balance)}, "
            f"erwartet {fmt_money(row.expected)}, "
            f"Differenz {fmt_money(row.difference)}. "
            "Quelle und Status: verifiziert (BC-Einrichtung)."
        )
    return " ".join(rendered)


def _bridge_table(report: Report) -> str:
    rows = []
    for label, month, ytd in _bridge_pairs(report):
        rows.append(
            (
                label,
                fmt_money(month.report),
                fmt_money(month.reference),
                fmt_money(month.difference),
                fmt_money(ytd.report),
                fmt_money(ytd.reference),
                fmt_money(ytd.difference),
            )
        )
    return _table(
        (
            "Position",
            "Monat Sachposten",
            "Monat Saldenliste",
            "Monat Differenz",
            "YTD Sachposten",
            "YTD Saldenliste",
            "YTD Differenz",
        ),
        rows,
    )


def _bridge_pairs(report: Report) -> tuple[tuple[str, Figure, Figure], ...]:
    order = (
        ("UMSATZ", "Umsatz"),
        ("WARENEINSATZ", "Wareneinsatz"),
        ("memo", "Rohertrag"),
        ("BETRIEBSAUFWAND", "Betriebsaufwand"),
        ("ABSCHREIBUNG", "Abschreibung"),
        ("SONSTIGER_ERTRAG_AUFWAND", "Sonstiger Ertrag und Aufwand"),
        ("ebit", "EBIT"),
        ("ZINS_FINANZ", "Zins und Finanz"),
        ("fehlbuchung", "davon Fehlbuchung Kundenzahlungen auf 4201"),
        ("STEUER", "Steuer"),
        ("LAGERZUGANG_VERRECHNUNG", "Lagerzugang Verrechnung"),
        ("NICHT_ZUGEORDNET", "Nicht zugeordnet"),
        ("sum", "Summe Überleitung"),
        ("guv", "Ergebnis GuV"),
        ("diff", "Differenz"),
    )
    pairs: list[tuple[str, Figure, Figure]] = []
    for key, label in order:
        if key == "fehlbuchung":
            month = report.revenue_cut_month or Figure(Decimal(0), Decimal(0))
            ytd = report.revenue_cut_ytd or Figure(Decimal(0), Decimal(0))
        elif key == "memo":
            month = Figure(
                report.bridge_month.buckets["UMSATZ"].report
                - report.bridge_month.buckets["WARENEINSATZ"].report,
                report.bridge_month.buckets["UMSATZ"].reference
                - report.bridge_month.buckets["WARENEINSATZ"].reference,
            )
            ytd = Figure(
                report.bridge_ytd.buckets["UMSATZ"].report
                - report.bridge_ytd.buckets["WARENEINSATZ"].report,
                report.bridge_ytd.buckets["UMSATZ"].reference
                - report.bridge_ytd.buckets["WARENEINSATZ"].reference,
            )
        elif key == "ebit":
            month, ytd = report.bridge_month.ebit, report.bridge_ytd.ebit
        elif key == "sum":
            month, ytd = report.bridge_month.total, report.bridge_ytd.total
        elif key == "guv":
            month, ytd = report.bridge_month.guv, report.bridge_ytd.guv
        elif key == "diff":
            month, ytd = report.bridge_month.difference, report.bridge_ytd.difference
        else:
            month = report.bridge_month.buckets[key]
            ytd = report.bridge_ytd.buckets[key]
        pairs.append((label, month, ytd))
    return tuple(pairs)


def _bridge_figures(bridge: Bridge) -> tuple[tuple[str, Figure], ...]:
    figures = [(BUCKET_LABEL[bucket], bridge.buckets[bucket]) for bucket in BUCKETS]
    figures.append(("EBIT", bridge.ebit))
    figures.append(("Summe Überleitung", bridge.total))
    figures.append(("Ergebnis GuV", bridge.guv))
    figures.append(("Differenz", bridge.difference))
    return tuple(figures)


def _value_table(report: Report) -> str:
    month = report.values_month
    ytd = report.values_ytd
    rows = (
        ("Verkaufsbetrag", month.sales_amount, ytd.sales_amount),
        ("Einstandsbetrag Verkauf", month.sales_cost, ytd.sales_cost),
        ("Umsatz FiBu", month.revenue, ytd.revenue),
        ("Wareneinsatz FiBu", month.cogs, ytd.cogs),
        (
            "Verkaufsbetrag minus Umsatz",
            month.sales_amount - month.revenue,
            ytd.sales_amount - ytd.revenue,
        ),
        ("Konto 4201 Soll minus Haben", month.account_4201, ytd.account_4201),
        ("Wareneinsatz plus Einstand", month.cogs + month.sales_cost, ytd.cogs + ytd.sales_cost),
    )
    return _table(
        ("Position", "Monat", "YTD"),
        tuple((label, fmt_money(left), fmt_money(right)) for label, left, right in rows),
    )


def _p5b_section(report: Report) -> list[str]:
    shown = [
        row
        for row in report.p5b
        if row.label.endswith("YTD") or row.label == report.as_of.strftime("%Y-%m")
    ]
    diffs = [row for row in report.p5b if not within(row.difference, report.tolerance)]
    lines = [
        "## P5b Wareneinsatz gegen Verkaufswertposten",
        "",
        "WARENEINSATZ aus der FiBu, nach Abzug der Lagerzugangsverrechnung, gegen minus Summe "
        "costPostedToGL der Verkaufswertposten. Je Monat und YTD, 2025 und 2026. Toleranz 0,00.",
        "",
        _table(
            ("Zeitraum", "Wareneinsatz FiBu", "Verkauf an FiBu", "Differenz"),
            tuple(
                (
                    row.label,
                    fmt_money(row.fibu),
                    fmt_money(row.reference),
                    fmt_money(row.difference),
                )
                for row in shown
            ),
        ),
        "",
    ]
    if diffs:
        lines.append("Monate mit Differenz:")
        lines.append("")
        lines.append(
            _table(
                ("Zeitraum", "Wareneinsatz FiBu", "Verkauf an FiBu", "Differenz"),
                tuple(
                    (
                        row.label,
                        fmt_money(row.fibu),
                        fmt_money(row.reference),
                        fmt_money(row.difference),
                    )
                    for row in diffs
                ),
            )
        )
        lines.append("")
    else:
        lines.append("Alle Monate und die YTD-Zeilen haben Differenz 0,00.")
        lines.append("")
    return lines


def _gl_fact(entry: GlEntry) -> str:
    source = plain(entry.source_code) or "ohne Quellcode"
    return (
        f"{fmt_date(entry.posting_date)} Beleg {entry.document_number or 'ohne'} "
        f"Soll {fmt_money(entry.debit)} Haben {fmt_money(entry.credit)}, "
        f"{plain(entry.description) or 'ohne Beschreibung'}, {source}"
    )


def _cogs_credit_note(books: Books, as_of: date) -> str:
    start = date(as_of.year - 1, 12, 31)
    lines = [
        entry
        for entry in books.gl
        if entry.account == "5021" and start < entry.posting_date <= as_of
    ]
    credits = [entry for entry in lines if entry.credit != 0]
    credit_sum = cents(sum((entry.credit for entry in credits), Decimal(0)))
    if credit_sum == 0:
        return (
            f"e) Konto 5021 hat {as_of.year} bis {fmt_date(as_of)} kein Haben. "
            "Eine Zerlegung der Habenseite entfällt."
        )
    credit_docs = {entry.document_number for entry in credits}
    same_debits = [
        entry for entry in lines if entry.document_number in credit_docs and entry.debit != 0
    ]
    ordered = sorted(credits, key=lambda entry: (entry.posting_date, entry.document_number))
    debit_ordered = sorted(
        same_debits, key=lambda entry: (entry.posting_date, entry.document_number)
    )
    pairs_ok = True
    for document in credit_docs:
        group = [entry for entry in lines if entry.document_number == document]
        debit = cents(sum((entry.debit for entry in group), Decimal(0)))
        credit = cents(sum((entry.credit for entry in group), Decimal(0)))
        pairs_ok = pairs_ok and debit == credit
    others = [
        entry
        for entry in lines
        if entry.debit == credit_sum and entry.document_number not in credit_docs
    ]
    exact_credit = any(entry.credit == credit_sum for entry in credits)
    head = (
        f"e) Konto 5021 hat {as_of.year} bis {fmt_date(as_of)} im Haben {fmt_money(credit_sum)}. "
    )
    if exact_credit:
        head += f"Ein Sachposten hat Haben {fmt_money(credit_sum)}. "
    else:
        head += f"Kein Sachposten hat Haben {fmt_money(credit_sum)}. "
    head += "Die Habenseite: " + "; ".join(_gl_fact(entry) for entry in ordered) + ". "
    if debit_ordered:
        head += "Soll auf denselben Belegen: " + "; ".join(
            _gl_fact(entry) for entry in debit_ordered
        )
        head += ". "
    if pairs_ok:
        head += (
            "Auf jedem dieser Belege ist das Soll auf 5021 gleich dem Haben. "
            "Die Posten heben sich belegweise auf. "
            "Ein einzelnes Soll-Haben-Paar über den Summenbetrag gibt es nicht. "
        )
    else:
        head += "Die Belege heben sich auf 5021 nicht vollständig auf. "
    if others:
        other_text = "; ".join(
            _gl_fact(entry)
            for entry in sorted(
                others, key=lambda entry: (entry.posting_date, entry.document_number)
            )
        )
        head += (
            f"Sollposten über {fmt_money(credit_sum)} auf anderen Belegen: {other_text}. "
            "Das sind nicht die Gegenbuchungen der Habenseite. "
        )
    clearing = _receipt_clearing(books.item_values, start, as_of)
    if clearing == 0:
        head += (
            "Diese Habenposten sind keine Zugänge der Art Positive Adjmt. oder Output. "
            "Sie bleiben in der Nettobewegung. "
            "Der Lagerzugang aus den Wertposten ist davon getrennt."
        )
    elif clearing == credit_sum:
        head += "Die Habenseite trifft die Lagerzugangsverrechnung aus den Artikelwertposten."
    else:
        head += (
            f"Lagerzugang aus den Wertposten {fmt_money(clearing)}, "
            f"Habenseite {fmt_money(credit_sum)}."
        )
    return head


def _mentioned_documents(text: str) -> set[str]:
    found: set[str] = set()
    current: list[str] = []
    for char in text + " ":
        if char.isdigit():
            current.append(char)
        else:
            if len(current) >= 5:
                found.add("".join(current))
            current = []
    return found


def _p8_evidence(books: Books, gaps: Sequence[DocumentGap]) -> str:
    kept = _residual_gaps(gaps)
    if not kept:
        return ""
    parts: list[str] = []
    for gap in kept:
        gl_lines = sorted(
            (entry for entry in books.gl if entry.document_number == gap.document),
            key=lambda entry: entry.entry_no,
        )
        gl_text = "; ".join(
            (
                f"Konto {entry.account} Soll {fmt_money(entry.debit)} "
                f"Haben {fmt_money(entry.credit)}, "
                f"{plain(entry.description) or 'ohne Beschreibung'}, "
                f"{plain(entry.source_code) or 'ohne Quellcode'}"
            )
            for entry in gl_lines
        )
        purchases = [row for row in books.purchases if row.document_number == gap.document]
        ledger_ids = {row.ledger_entry_no for row in purchases if row.ledger_entry_no}
        ledgers = [row for row in books.item_ledger if row.entry_no in ledger_ids]
        values = [row for row in books.item_values if row.entry_no in ledger_ids]
        if not values and ledgers:
            keys = {
                (row.item_no, row.posting_date, row.item_ledger_type.casefold()) for row in ledgers
            }
            values = [
                row
                for row in books.item_values
                if (row.item_no, row.posting_date, row.item_ledger_type.casefold()) in keys
            ]
        purchase_text = "; ".join(
            (
                f"Einkaufswertposten {row.entry_no} Artikel {row.item_no or 'ohne'} "
                f"{row.entry_type or 'ohne Art'} costAmountActual {fmt_money(row.cost_actual)} "
                f"Artikelposten {row.ledger_entry_no or 'ohne'}"
            )
            for row in purchases
        )
        ledger_text = "; ".join(
            (
                f"Artikelposten {row.entry_no} Beleg {row.document_number or 'ohne'} "
                f"{row.entry_type or 'ohne Art'} {plain(row.document_type) or 'ohne Belegart'} "
                f"Artikel {row.item_no or 'ohne'} Menge {fmt_money(row.quantity)} "
                f"Einstand {fmt_money(row.cost_actual)}"
            )
            for row in ledgers
        )
        value_text = "; ".join(
            (
                f"Artikelwertposten {row.entry_no} Artikel {row.item_no or 'ohne'} "
                f"{row.item_ledger_type or 'ohne Art'} Einstand {fmt_money(row.cost_actual)} "
                f"an FiBu {fmt_money(row.cost_posted)}"
            )
            for row in values
        )
        item_bits: list[str] = []
        for number in sorted({row.item_no for row in purchases + ledgers if row.item_no}):
            item = books.items.get(number)
            if item is None:
                item_bits.append(f"Artikel {number} ohne Stamm im Snapshot")
                continue
            stock_group = item.inventory_group or "leer"
            product_group = item.product_group or "leer"
            item_bits.append(
                f"Artikel {item.number} {item.name}, Typ {item.item_type or 'leer'}, "
                f"Produktbuchungsgruppe {product_group}, Lagerbuchungsgruppe {stock_group}"
            )
        mentioned = _mentioned_documents(" ".join(entry.description for entry in gl_lines))
        ledger_docs = {row.document_number for row in ledgers}
        foreign = sorted(mentioned - ledger_docs - {gap.document})
        foreign_bits: list[str] = []
        for number in foreign:
            hits = [row for row in books.item_ledger if row.document_number == number]
            if not hits:
                foreign_bits.append(f"Beleg {number} aus der Beschreibung hat keinen Artikelposten")
                continue
            sample = hits[0]
            foreign_bits.append(
                f"Beleg {number} aus der Beschreibung ist Artikelposten {sample.entry_no}, "
                f"Artikel {sample.item_no or 'ohne'}, {sample.entry_type or 'ohne Art'}"
            )
        cause = (
            "Die Differenz sitzt auf dem Bestandskonto des Belegs. "
            "Der zugehörige Wertposten und der Artikelposten haben Einstand 0,00. "
        )
        if any("kein Lager" in bit.casefold() or "Non-Inventory" in bit for bit in item_bits):
            cause += "Der Artikel ist kein Lagerartikel. "
        cause += (
            "Warum die FiBu das Bestandskonto belastet, steht in der Buchungsmatrix. "
            "Die liegt nicht im Snapshot. Die Ursache ist damit nicht eindeutig."
        )
        if foreign_bits:
            cause += " " + " ".join(foreign_bits) + "."
        parts.append(
            f"Beleg {gap.document}. Sachposten: {gl_text or 'keine'}. "
            f"Wertposten: {purchase_text or 'keine'}; {value_text or 'kein Artikelwertposten'}. "
            f"Artikelposten: {ledger_text or 'keine'}. "
            f"{' '.join(item_bits)}. {cause}"
        )
    return " ".join(parts)


def _findings(report: Report) -> list[str]:
    paragraphs = [
        _finding_a(report),
        _finding_b(report),
        _finding_c(report),
        _finding_d(report),
        report.cogs_note,
        _finding_cutoff(report),
        _finding_p8(report),
    ]
    return paragraphs


def _finding_a(report: Report) -> str:
    groups = ", ".join(
        f"{ledger_type} / {document_type}: {count} Posten, Einstand {fmt_money(actual)}, an FiBu "
        f"{fmt_money(posted)}"
        for ledger_type, document_type, count, actual, posted in report.value_groups_2025
        if actual != 0
    )
    ledgers = ", ".join(
        f"{entry_type} Beleg {document}: {count} Posten, Einstand {fmt_money(amount)}"
        for entry_type, document, count, amount in report.ledger_groups_2025
        if entry_type == "Positive Adjmt."
    )
    date_text = fmt_date(report.standard_date) if report.standard_date else "ohne Datum"
    return (
        "a) Konto 5021 hat 2025 im Haben "
        f"{fmt_money(report.credit_5021_2025)}. Davon stehen {fmt_money(report.standard_credit)} "
        f"auf {report.standard_lines} Sachposten mit Beleg STANDARD, Quellcode LWERTBUCH, "
        f"Buchungsdatum {date_text}. "
        "Die Beschreibung in der FiBu lautet Direkte Kosten. "
        f"Artikelwertposten 2025 mit Betrag: {groups or 'keine'}. "
        "Die API der Artikelwertposten hat in diesem Katalog kein Feld Eintragsart und keine "
        "Belegnummer. "
        f"Die Artikelposten dazu: {ledgers or 'keine'}. "
        "Positive Adjmt. mit Beleg STANDARD ist ein Artikelbuchblatt, keine Einkaufsrechnung, und "
        "costPostedToGL trifft den Einstand. "
        + (
            "Die Lagerzugangsverrechnung 2025 aus costPostedToGL trifft diese Habenseite. "
            if report.receipt_2025 == report.credit_5021_2025
            else (
                "Die Lagerzugangsverrechnung 2025 aus costPostedToGL ist "
                f"{fmt_money(report.receipt_2025)} und weicht von der Habenseite ab. "
            )
        )
        + (
            "Das Lagerkorrekturkonto der Buchungsmatrix HANDEL ist 5021. "
            "Das erklärt die Habenbuchung des Anfangsbestands 2025 auf 5021."
            if "Lagerkorrekturkonto" in report.inventory.note
            else (
                "Hypothese: Anfangsbestand oder Zugang ohne Einkaufsrechnung über das "
                "Artikelbuchblatt der Demofirma. Ein Kennzeichen Anfangsbestand steht an den "
                "Posten nicht."
            )
        )
    )


def _finding_b(report: Report) -> str:
    ytd = report.values_ytd
    gap = cents(ytd.sales_amount - ytd.revenue)
    name = next((row.name for row in report.movement if row.account == "4201"), "4201")
    return (
        "b) Erlöse FiBu gegen Verkaufsbetrag, YTD. Verkaufsbetrag "
        f"{fmt_money(ytd.sales_amount)}, Umsatz {fmt_money(ytd.revenue)}, Differenz "
        f"{fmt_money(gap)}. "
        "4201 liegt im Finanzergebnis, nicht im Umsatz. "
        f"Soll minus Haben auf 4201 ist {fmt_money(ytd.account_4201)}. "
        "Die Posten sind Kundenzahlungen, Belegart Payment, Quellcode FIBUBUCHBL, Herkunft "
        "Customer. Belegnummern 103199 bis 103214, Beschreibung 102206 bis 102221. "
        "Fehlbuchung der Demodaten. Sie wird nicht im Umsatz korrigiert. "
        f"Der Kontoname ({plain(name)}) passt nicht zur Buchung."
    )


def _finding_c(report: Report) -> str:
    parts = [
        "c) Dimensionen auf GuV-Posten. "
        f"Abteilung {fmt_share(report.with_department, report.guv_entries)}, "
        f"Debitorengruppe {fmt_share(report.with_customer_group, report.guv_entries)}. "
        "Nicht zugeordnet heißt: das Dimensionsset des Postens trägt die Dimension nicht."
    ]
    for bucket, (count, missing, amount, missing_amount) in report.kpi_unassigned.items():
        if count == 0:
            parts.append(f"{BUCKET_LABEL[bucket]} YTD: keine Posten.")
            continue
        amount_share = "0,0 %" if amount == 0 else _amount_share(missing_amount, amount)
        parts.append(
            f"{BUCKET_LABEL[bucket]} YTD ohne Abteilung: {fmt_share(missing, count)}, Betrag "
            f"{amount_share}."
        )
    return " ".join(parts)


def _finding_d(report: Report) -> str:
    body = " ".join(report.category_notes)
    return (
        "d) Kategorienlücken in BC. "
        + body
        + " 60410 hat Bewegung und liegt deshalb im Betriebsaufwand, die fünf Konten ohne Bewegung "
        "bleiben ohne Bucket-Wirkung."
    )


def _finding_cutoff(report: Report) -> str:
    protocol = _span(report.after_protocol, report.after_protocol_from, report.after_protocol_to)
    snapshot = _span(report.after_snapshot, report.after_snapshot_from, report.after_snapshot_to)
    return (
        f"Posten nach dem Stichtag dieses Protokolls: {protocol}. "
        f"Posten nach dem Stichtag des Snapshots: {snapshot}. "
        "Sie fließen in keinen Periodenwert. Differenzen werden nicht gegengerechnet."
    )


def _gap_text(item: DocumentGap) -> str:
    kind = item.entry_type or "ohne"
    ledger = item.item_ledger_type or "ohne"
    item_no = item.item_no or "ohne"
    return (
        f"Beleg {item.document} am {fmt_date(item.posting_date)}, "
        f"FiBu {fmt_money(item.gl_amount)}, Artikelposten {fmt_money(item.ledger_amount)}, "
        f"Artikel {item_no}, Eintragsart {kind}, Artikelpostenart {ledger}"
    )


def _known_cause(report: Report) -> str:
    matches = [
        item
        for item in report.known
        if item.check_id == "P8" and cents(item.amount) == cents(report.p8.difference)
    ]
    if matches:
        item = matches[0]
        return (
            f"Ursache: {item.cause} Quelle: {item.source}. "
            f"Beleg {item.document}, Artikel {item.item}. "
            "Status: erklärt. Der Betrag bleibt stehen und wird nicht verrechnet."
        )
    known = [item for item in report.known if item.check_id == "P8"]
    if not known:
        return "Status: offen. Der Betrag bleibt stehen."
    listed = ", ".join(fmt_money(item.amount) for item in known)
    return (
        f"Status: Differenz. Bekannter Betrag {listed}, Ist {fmt_money(report.p8.difference)}. "
        "Der Betrag wird nicht verrechnet."
    )


def _finding_p8(report: Report) -> str:
    if within(report.p8.difference, report.tolerance):
        return (
            "P8 Bestandswert trifft den Saldo der Lagerkonten. "
            f"costAmountActual minus costPostedToGL ist {fmt_money(report.p8_cost_gap)}."
        )
    kept = _residual_gaps(report.inventory_gaps)
    kept_documents = {item.document for item in kept}
    others = len(report.inventory_gaps) - len(kept)
    other_sum = cents(
        sum(
            (
                item.difference
                for item in report.inventory_gaps
                if item.document not in kept_documents
            ),
            Decimal(0),
        )
    )
    details = "; ".join(_gap_text(item) for item in kept)
    noise = ""
    if others and other_sum == 0:
        noise = (
            f"Belegweise weichen {len(report.inventory_gaps)} Belege ab. "
            f"{others} davon heben sich in der Summe auf ({fmt_money(other_sum)}). "
            "Artikelposten und FiBu führen für dieselbe Rechnung unterschiedliche Belegnummern, "
            "Verkauf 102 gegen 103, Einkauf 107 gegen 108. "
        )
    return (
        f"P8 Differenz {fmt_money(report.p8.difference)}. "
        f"costAmountActual minus costPostedToGL ist {fmt_money(report.p8_cost_gap)}, "
        "eine nicht gebuchte Lagerregulierung ist das damit nicht. "
        + noise
        + f"Übrig bleibt {details or 'kein einzelner Beleg'}. "
        + (report.p8_evidence + " " if report.p8_evidence else "")
        + _known_cause(report)
    )


def _residual_gaps(gaps: Sequence[DocumentGap]) -> tuple[DocumentGap, ...]:
    total = cents(sum((item.difference for item in gaps), Decimal(0)))
    if total == 0:
        return gaps
    for item in gaps:
        rest = cents(
            sum((row.difference for row in gaps if row.document != item.document), Decimal(0))
        )
        if rest == 0 and item.difference == total:
            return (item,)
    return gaps


def _method(report: Report) -> list[str]:
    p9_rows = tuple(
        (
            item.entity,
            item.route,
            str(item.snapshot_rows),
            str(item.manifest_rows),
            "",
            str(item.difference),
        )
        for item in report.counts
    )
    p9_gap = sum(abs(item.difference) for item in report.counts)
    closing = next(
        (
            item.snapshot_rows
            for item in report.counts
            if item.entity == "closingGeneralLedgerEntries"
        ),
        0,
    )
    return [
        f"P1 Summe Soll minus Summe Haben über alle Sachposten: {fmt_money(report.p1)}.",
        "P2 je Buchungskonto: Summe der Sachposten im Monat gegen Endsaldo Monatsende minus "
        "Endsaldo Vormonatsende.",
        "P3 je Buchungskonto: Summe der Sachposten bis zum Stichtag gegen balanceAtDateDebit minus "
        "balanceAtDateCredit.",
        "P4 Umsatz ist minus die Nettobewegung des Buckets UMSATZ. "
        "4730 und 4770 bleiben als Erlösminderung im Umsatz. 4201 liegt im Finanzergebnis.",
        "P5 EBIT aus den GuV-Buckets ohne Zins, Steuer, Lagerzugang Verrechnung und Nicht "
        "zugeordnet. Die Überleitung oben muss 0,00 ergeben.",
        "Konto 5021 hat eine Zeile NETTO. Wareneinsatz ist die Nettobewegung plus "
        "costPostedToGL der Artikelwertposten mit Artikelpostenart Positive Adjmt. oder Output. "
        "Das ist die Nettobewegung minus denselben Betrag mit Habenvorzeichen. "
        "Im Bericht steht der Lagerzugang positiv. Derselbe Betrag wird auf Sachposten und "
        "Saldenliste angesetzt, damit P5 die beiden Wege vergleicht.",
        "P5b stellt diesen Wareneinsatz gegen minus Summe costPostedToGL der Verkaufswertposten, "
        "je Monat und YTD, für 2025 und 2026. Toleranz 0,00.",
        "YTD ist Endsaldo Stichtag minus Endsaldo 31.12. des Vorjahres. Der Jahresanker 01.01.2024 "
        "bis 31.12.2024 liegt in derselben Saldenliste.",
        "P6 offene Forderungen aus dcleAmountLCY mit dclePostingDate bis zum Stichtag, je "
        "cleEntryNo, offen ab 0,01. Gegen Saldo der Forderungskonten.",
        "P7 analog mit dvleAmountLCY. Im Bericht positiv.",
        "P8 Summe costAmountActual der Artikelwertposten mit Buchungsdatum bis zum Stichtag gegen "
        "den Saldo der Lagerkonten. Eine bekannte Differenz bleibt stehen. Stimmt sie exakt mit "
        "einem Eintrag in bekannte_differenzen, ist der Status erklärt. Weicht sie ab, ist der "
        "Status Differenz. Die Toleranz bleibt 0,00, der Betrag wird nicht verrechnet.",
        "P9 Zeilen im Snapshot minus Zeilen in manifest.json. Summe der absoluten Abweichungen "
        f"{p9_gap}. Die Spalte Modell ist leer und kommt mit AP-04.",
        "",
        _table(("Entität", "Route", "Snapshot", "manifest", "Modell", "Differenz"), p9_rows),
        "",
        "Quellen: v2.0 generalLedgerEntries, accounts, trialBalances. Analytics "
        "incomeStatementGeneralLedgerEntries, balanceSheetGeneralLedgerEntries, "
        "customerLedgerEntries, vendorLedgerEntries, salesValueEntries, itemValueEntries, "
        "itemLedgerEntries, purchaseValueEntries, generalLedgerAccounts, "
        "generalLedgerAccountCategories, dynamicDimensions. Kein Aufruf während dieses Laufs.",
        f"Abschlussbuchungen: closingGeneralLedgerEntries hat {closing} Zeilen. "
        "GuV-Salden werden nicht als Periodenwert gelesen, weil keine Abschlussbuchungen die "
        "Salden auf null setzen.",
    ]


def _span(count: int, start: date | None, end: date | None) -> str:
    if count == 0 or start is None or end is None:
        return "0"
    return f"{count}, {fmt_date(start)} bis {fmt_date(end)}"


def _amount_share(part: Decimal, whole: Decimal) -> str:
    if whole == 0:
        return "0,0 %"
    pct = (part * Decimal(100) / whole).quantize(Decimal("0.1"))
    return f"{pct:.1f}".replace(".", ",") + " %"


def _month_name(day: date) -> str:
    months = (
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
    return f"{months[day.month - 1]} {day.year}"


def _dot(value: Decimal) -> str:
    return f"{cents(value):.2f}"


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
