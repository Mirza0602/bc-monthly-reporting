"""P1 to P9 on a handwritten fixture and on the CRONUS snapshot."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from src.reconcile import (
    AccountList,
    Books,
    ChartAccount,
    Config,
    CostLine,
    Detail,
    GlEntry,
    MappingRow,
    SalesLine,
    TrialPoint,
    build_report,
    load_books,
    load_config,
    load_mapping,
    render_markdown,
    status_label,
    write_protocol,
)
from src.trial_balance import month_end

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "snapshots" / "2026-10-24"
WHEN = datetime(2026, 10, 24, 18, 45)


def test_known_difference_status_is_exact() -> None:
    tolerance = Decimal("0.00")
    known = (Decimal("-240.00"),)
    assert status_label(Decimal("-240.00"), tolerance, known=known) == "erklärt"
    assert status_label(Decimal("-241.00"), tolerance, known=known) == "Differenz"
    assert status_label(Decimal("0.00"), tolerance, known=known) == "abgeglichen"
    assert status_label(Decimal("-240.00"), tolerance) == "offen"


def test_fixture_reconciles_month_and_ytd() -> None:
    report = build_report(_books(), _mapping(), _config(), date(2026, 2, 28), WHEN)
    assert report.p1 == 0
    assert report.p4_month.report == Decimal("50.00")
    assert report.p4_month.difference == 0
    assert report.p4_ytd.report == Decimal("150.00")
    assert report.p4_ytd.difference == 0
    assert report.p5_month.report == Decimal("38.00")
    assert report.p5_ytd.report == Decimal("98.00")
    assert report.p5_month.difference == 0
    assert report.p5_ytd.difference == 0
    assert report.bridge_ytd.buckets["LAGERZUGANG_VERRECHNUNG"].report == Decimal("10.00")
    assert report.bridge_ytd.buckets["WARENEINSATZ"].report == Decimal("40.00")
    assert all(row.difference == 0 for row in report.p5b)
    assert report.bridge_ytd.difference.report == 0
    assert report.bridge_ytd.difference.reference == 0
    assert report.bridge_month.difference.report == 0
    assert report.p6.report == Decimal("120.00")
    assert report.p6.difference == 0
    assert report.p7.report == Decimal("20.00")
    assert report.p7.difference == 0
    assert report.p8.report == Decimal("-30.00")
    assert report.p8.difference == 0
    assert report.p8_cost_gap == 0
    assert report.after_protocol == 2
    assert all(row.p2.difference == 0 and row.p3.difference == 0 for row in report.accounts)
    text = render_markdown(report)
    assert "\u2013" not in text and "\u2014" not in text
    assert "CRONUS DE" in text
    assert "vorläufig" in text


def test_unmapped_income_lands_in_the_bridge() -> None:
    books = _books()
    books.gl = books.gl + (
        GlEntry("90", "4985", date(2026, 2, 2), Decimal("10"), Decimal(0)),
        GlEntry("91", "2000", date(2026, 2, 2), Decimal(0), Decimal("10")),
    )
    books.chart["4985"] = ChartAccount("4985", "Sonstiges", "Posting", True)
    books.trial = books.trial + (
        _point("4985", date(2026, 2, 1), date(2026, 2, 28), "10", "0", "10"),
        _point("4985", date(2026, 1, 1), date(2026, 1, 31), "0", "0", "0"),
        _point("4985", date(2025, 12, 1), date(2025, 12, 31), "0", "0", "0"),
    )
    books.trial = tuple(
        _point("2000", date(2026, 2, 1), date(2026, 2, 28), "50", "22", "28")
        if point.account == "2000" and point.end == date(2026, 2, 28)
        else point
        for point in books.trial
    )
    report = build_report(books, _mapping(), _config(), date(2026, 2, 28), WHEN)
    assert report.bridge_month.buckets["NICHT_ZUGEORDNET"].report == Decimal("-10.00")
    assert report.p5_month.report == Decimal("38.00")
    assert report.bridge_month.difference.report == 0
    assert report.bridge_month.difference.reference == 0


def test_mapping_file_covers_each_account_once() -> None:
    rows = load_mapping(ROOT / "config" / "kpi_mapping.csv")
    rules: dict[str, set[str]] = {}
    for row in rows:
        rules.setdefault(row.account, set()).add(row.rule)
    assert rules["5021"] == {"NETTO"}
    assert all(len(group) == 1 for group in rules.values())
    assert len(rows) == 98
    by_account = {row.account: row for row in rows}
    assert by_account["5021"].bucket == "WARENEINSATZ"
    assert "Zerlegung" in by_account["5021"].note
    assert by_account["4203"].bucket == "ZINS_FINANZ"
    assert by_account["4201"].bucket == "ZINS_FINANZ"
    assert by_account["4201"].sign == -1
    assert by_account["4201"].note.startswith("Entscheidung 24.10.2026")
    assert by_account["7400"].bucket == "SONSTIGER_ERTRAG_AUFWAND"
    assert by_account["7400"].sign == -1
    assert "4730 und 4770 bleiben als Erlösminderung im Umsatz." in by_account["4730"].note
    assert "4730 und 4770 bleiben als Erlösminderung im Umsatz." in by_account["4770"].note
    for number in ("5032", "5033", "5034", "5035", "5036", "5037"):
        assert by_account[number].bucket == "WARENEINSATZ"
        assert by_account[number].note.startswith("Abweichungskonto")


def test_config_marks_the_account_lists_verified() -> None:
    config = load_config(ROOT / "config" / "reconciliation.yaml")
    assert config.tolerance == 0
    assert config.receivables.numbers == ("1202", "1203")
    assert config.payables.numbers == ("3301", "3302")
    assert config.inventory.numbers == ("1001", "1101", "1102")
    assert config.receivables.status == "verifiziert"
    assert config.payables.status == "verifiziert"
    assert config.inventory.status == "verifiziert"
    assert config.receivables.source == "BC-Einrichtung"
    assert config.zero_accounts is not None
    assert config.zero_accounts.numbers == ("1085",)
    assert config.zero_accounts.expected == 0
    assert {f"P{index}" for index in range(1, 10)} <= {item[0] for item in config.checks}
    assert "P5b" in {item[0] for item in config.checks}
    assert "Lagerkorrekturkonto" in config.inventory.note
    assert len(config.known) == 1
    assert config.known[0].check_id == "P8"
    assert config.known[0].amount == Decimal("-240.00")
    assert config.known[0].document == "108210"
    assert config.known[0].status == "erklaert"


def test_snapshot_accepts_both_months() -> None:
    books = load_books(SNAPSHOT)
    config = load_config(ROOT / "config" / "reconciliation.yaml")
    mapping = load_mapping(ROOT / "config" / "kpi_mapping.csv")
    folder = ROOT / "docs" / "abstimmung"
    september = None
    for as_of in (date(2026, 9, 30), date(2026, 8, 31)):
        report = write_protocol(books, mapping, config, as_of, WHEN, folder)
        assert report.p1 == 0
        assert report.p4_month.difference == 0
        assert report.p4_ytd.difference == 0
        assert report.p5_month.difference == 0
        assert report.p5_ytd.difference == 0
        assert report.p6.difference == 0
        assert report.p7.difference == 0
        assert report.bridge_month.difference.report == 0
        assert report.bridge_month.difference.reference == 0
        assert report.bridge_ytd.difference.report == 0
        assert report.bridge_ytd.difference.reference == 0
        assert all(row.p2.difference == 0 and row.p3.difference == 0 for row in report.accounts)
        assert all(item.difference == 0 for item in report.counts)
        assert report.p8_explained
        path = folder / f"Abstimmprotokoll_{as_of.strftime('%Y-%m')}.md"
        text = path.read_text(encoding="utf-8")
        assert "\u2013" not in text and "\u2014" not in text
        assert "Modell" in text
        if as_of == date(2026, 9, 30):
            september = report
            assert report.after_snapshot == 48
            assert "8,1 %" in text
            assert "87,2 %" in text
            assert "verifiziert (BC-Einrichtung)" in text
            assert "Prüfkonto 1085" in text
            assert "Abweichungskonten" in text
            assert report.zero_balances[0].difference == 0
            assert report.bridge_month.buckets["WARENEINSATZ"].report == Decimal("5434.00")
            assert report.p4_month.report == Decimal("6966.00")
            assert report.p5_month.report == Decimal("-8528.00")
            assert report.p4_ytd.report == Decimal("362007.38")
            assert report.bridge_ytd.buckets["WARENEINSATZ"].report == Decimal("260374.20")
            assert report.bridge_ytd.buckets["ZINS_FINANZ"].report == Decimal("-26244.83")
            assert report.bridge_ytd.buckets["LAGERZUGANG_VERRECHNUNG"].report == Decimal("0.00")
            assert report.p5_ytd.report == Decimal("86973.18")
            assert report.bridge_ytd.guv.report == Decimal("60728.35")
            gross = (
                report.bridge_ytd.buckets["UMSATZ"].report
                - report.bridge_ytd.buckets["WARENEINSATZ"].report
            )
            assert gross == Decimal("101633.18")
            assert report.values_ytd.sales_amount - report.values_ytd.revenue == 0
        if as_of == date(2026, 8, 31):
            assert report.bridge_month.buckets["WARENEINSATZ"].report == Decimal("42313.80")
            assert report.bridge_ytd.buckets["WARENEINSATZ"].report == Decimal("254940.20")
            assert report.bridge_ytd.buckets["LAGERZUGANG_VERRECHNUNG"].report == Decimal("0.00")
            assert report.p5_ytd.report == Decimal("95501.18")
            assert report.bridge_ytd.guv.report == Decimal("69256.35")
        assert report.p8_status == "erklärt"
        assert all(row.difference == 0 for row in report.p5b)
        assert "davon Fehlbuchung Kundenzahlungen auf 4201" in text
        assert "davon Erlösminderung durch Zahlungsbuchungen (4201)" not in text
        assert "Wertpapieren" in text
        assert "Status: erklärt" in text
    assert september is not None
    assert september.p8.difference == Decimal("-240.00")
    assert september.p8_cost_gap == 0
    assert september.receipt_2025 == Decimal("2185565.50")
    assert any(item.document == "108210" for item in september.inventory_gaps)
    moved = {(row.account, row.bucket) for row in september.movement}
    assert ("5021", "WARENEINSATZ") in moved
    assert ("5021", "LAGERZUGANG_VERRECHNUNG") not in moved
    assert ("4201", "ZINS_FINANZ") in moved
    assert ("4201", "UMSATZ") not in moved
    assert ("6220", "ABSCHREIBUNG") in moved
    assert ("60410", "BETRIEBSAUFWAND") in moved


def test_manifest_still_has_no_company_id() -> None:
    text = (SNAPSHOT / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(text)
    assert manifest["company"] == "CRONUS DE"
    assert "companyId" not in text


def _config() -> Config:
    accounts = AccountList("P6", ("1202",), "Test", "vorläufig", "Test.")
    payables = AccountList("P7", ("3301",), "Test", "vorläufig", "Test.")
    inventory = AccountList("P8", ("1001",), "Test", "vorläufig", "Test.")
    checks = tuple((f"P{index}", f"P{index}") for index in range(1, 10))
    return Config(Decimal("0.00"), None, accounts, payables, inventory, checks)


def _mapping() -> tuple[MappingRow, ...]:
    return (
        MappingRow("4403", "Umsatz", "UMSATZ", "NETTO", -1, "test", ""),
        MappingRow("5021", "Material", "WARENEINSATZ", "NETTO", 1, "test", ""),
        MappingRow("6220", "AfA", "ABSCHREIBUNG", "NETTO", 1, "test", ""),
        MappingRow("6825", "Recht", "BETRIEBSAUFWAND", "NETTO", 1, "test", ""),
    )


def _books() -> Books:
    gl = (
        *_pair("1", date(2026, 1, 15), "1202", "4403", "100"),
        *_pair("3", date(2026, 1, 15), "5021", "1001", "40"),
        *_pair("5", date(2026, 1, 15), "1001", "5021", "10"),
        *_pair("7", date(2026, 2, 10), "1202", "4403", "50"),
        *_pair("9", date(2026, 2, 10), "6220", "2000", "5"),
        *_pair("11", date(2026, 2, 10), "6825", "2000", "7"),
        *_pair("13", date(2026, 2, 10), "2000", "3301", "20"),
        *_pair("15", date(2026, 2, 12), "2000", "1202", "30"),
        GlEntry("17", "6825", date(2026, 2, 12), Decimal("1"), Decimal(0)),
        GlEntry("18", "6825", date(2026, 2, 12), Decimal(0), Decimal("1")),
        *_pair("19", date(2026, 3, 5), "6825", "2000", "3"),
    )
    assert len(gl) == 20
    chart = {
        number: ChartAccount(number, number, "Posting", number in {"4403", "5021", "6220", "6825"})
        for number in _accounts()
    }
    return Books(
        gl=gl,
        trial=(*_zeros(date(2025, 12, 31)), *_january(), *_february()),
        chart=chart,
        customers=(
            Detail("1", date(2026, 1, 15), Decimal("100")),
            Detail("2", date(2026, 2, 10), Decimal("50")),
            Detail("1", date(2026, 2, 12), Decimal("-30")),
        ),
        vendors=(Detail("9", date(2026, 2, 10), Decimal("-20")),),
        item_values=(
            CostLine(date(2026, 1, 15), Decimal("-40"), Decimal("-40")),
            CostLine(
                date(2026, 1, 15),
                Decimal("10"),
                Decimal("10"),
                item_ledger_type="Positive Adjmt.",
            ),
            CostLine(date(2026, 3, 5), Decimal("999"), Decimal("999")),
        ),
        item_ledger=(
            CostLine(date(2026, 1, 15), Decimal("-40"), document_number="3"),
            CostLine(date(2026, 1, 15), Decimal("10"), document_number="5"),
        ),
        sales=(
            SalesLine(date(2026, 1, 15), Decimal("100"), Decimal("-40"), Decimal("-40")),
            SalesLine(date(2026, 2, 10), Decimal("50"), Decimal(0), Decimal(0)),
        ),
        company="CRONUS DE",
        environment="Production",
        stand="24.10.2026",
        snapshot_name="fixture",
        snapshot_cutoff=date(2026, 2, 28),
    )


def _pair(
    start: str,
    posted: date,
    debit: str,
    credit: str,
    amount: str,
) -> tuple[GlEntry, GlEntry]:
    number = int(start)
    value = Decimal(amount)
    return (
        GlEntry(str(number), debit, posted, value, Decimal(0), document_number=str(number)),
        GlEntry(str(number + 1), credit, posted, Decimal(0), value, document_number=str(number)),
    )


def _point(
    account: str,
    start: date,
    end: date,
    debit: str,
    credit: str,
    balance: str,
) -> TrialPoint:
    return TrialPoint(
        account,
        account,
        "Posting",
        start,
        end,
        Decimal(debit),
        Decimal(credit),
        Decimal(balance),
    )


def _zeros(end: date) -> tuple[TrialPoint, ...]:
    start = end.replace(day=1)
    return tuple(_point(account, start, end, "0", "0", "0") for account in _accounts())


def _january() -> tuple[TrialPoint, ...]:
    end = date(2026, 1, 31)
    start = date(2026, 1, 1)
    values = {
        "4403": ("0", "100", "-100"),
        "5021": ("40", "10", "30"),
        "1001": ("10", "40", "-30"),
        "1202": ("100", "0", "100"),
    }
    return tuple(
        _point(account, start, end, *values.get(account, ("0", "0", "0")))
        for account in _accounts()
    )


def _february() -> tuple[TrialPoint, ...]:
    end = month_end(2026, 2)
    start = date(2026, 2, 1)
    values = {
        "4403": ("0", "50", "-150"),
        "5021": ("0", "0", "30"),
        "6220": ("5", "0", "5"),
        "6825": ("8", "1", "7"),
        "1001": ("0", "0", "-30"),
        "1202": ("50", "30", "120"),
        "2000": ("50", "12", "38"),
        "3301": ("0", "20", "-20"),
    }
    return tuple(_point(account, start, end, *values[account]) for account in _accounts())


def _accounts() -> tuple[str, ...]:
    return ("4403", "5021", "6220", "6825", "1001", "1202", "2000", "3301")
