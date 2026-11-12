"""Tests for the AP-01 calculations. No network."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from src.datenbestand import (
    AccountInfo,
    DetailRow,
    DimensionMaster,
    GlRow,
    RouteAssessment,
    TrialRow,
    accounts_without_category,
    assert_no_secrets,
    build_profile,
    category_label,
    compare_trial,
    default_as_of,
    open_at,
    parse_amount,
    parse_metadata,
    period_totals,
    recommend,
    render_feldinventar,
    render_profile,
    sign_check,
    write_manifest,
    write_snapshot_table,
)

METADATA = """<?xml version="1.0" encoding="utf-8"?>
<edmx:Edmx xmlns:edmx="http://docs.oasis-open.org/odata/ns/edmx" Version="4.0">
  <edmx:DataServices>
    <Schema xmlns="http://docs.oasis-open.org/odata/ns/edm" Namespace="Microsoft.NAV">
      <EnumType Name="incomeBalance">
        <Member Name="Income Statement" Value="0" />
        <Member Name="Balance Sheet" Value="1" />
      </EnumType>
      <EntityType Name="generalLedgerEntry">
        <Key><PropertyRef Name="id" /></Key>
        <Property Name="id" Type="Edm.Guid" Nullable="false" />
        <Property Name="amount" Type="Edm.Decimal" Scale="2" />
        <Property Name="incomeBalance" Type="Microsoft.NAV.incomeBalance" />
        <NavigationProperty Name="dimensionSetLines"
          Type="Collection(Microsoft.NAV.dimensionSetLine)" />
      </EntityType>
      <EntityContainer Name="NAV">
        <EntitySet Name="generalLedgerEntries" EntityType="Microsoft.NAV.generalLedgerEntry" />
      </EntityContainer>
    </Schema>
  </edmx:DataServices>
</edmx:Edmx>
"""


def test_category_label_decodes_odata_names() -> None:
    assert category_label("Cost_x0020_of_x0020_Goods_x0020_Sold") == "Wareneinsatz"
    assert category_label("Income") == "Einnahmen"
    assert category_label("_x0020_") == ""
    assert category_label("Einnahmen") == "Einnahmen"
    assert parse_amount("72,893.84") == Decimal("72893.84")
    assert parse_amount("72.893,84") == Decimal("72893.84")
    assert parse_amount("(1.234,56)") == Decimal("-1234.56")
    assert parse_amount("-10,5") == Decimal("-10.5")
    assert parse_amount("") == Decimal(0)
    assert parse_amount(Decimal("1.25")) == Decimal("1.25")


def test_default_cutoff_is_the_previous_month_end() -> None:
    assert default_as_of(date(2026, 10, 24)) == date(2026, 9, 30)


def test_open_amount_ignores_details_after_the_cutoff() -> None:
    rows = [
        DetailRow("1", "C1", date(2026, 1, 1), Decimal("100")),
        DetailRow("1", "C1", date(2026, 10, 1), Decimal("-100")),
        DetailRow("2", "C2", date(2026, 2, 1), Decimal("40")),
    ]
    result = open_at(rows, date(2026, 9, 30))
    assert result.entries == 2
    assert result.parties == 2
    assert result.amount == Decimal("140.00")


def test_debit_and_credit_balance() -> None:
    rows = [
        GlRow(date(2026, 1, 1), Decimal("10"), "4000", "guv", "1"),
        GlRow(date(2026, 1, 2), Decimal("-4"), "4000", "guv", "2"),
        GlRow(date(2026, 2, 1), Decimal("-6"), "5000", "guv", "3"),
    ]
    months = period_totals(rows, monthly=True)
    assert months[0].debit == Decimal("10")
    assert months[0].credit == Decimal("4")
    assert months[0].balance == Decimal("6")
    assert sum((item.balance for item in months), Decimal(0)) == Decimal(0)


def test_trial_balance_difference_uses_cumulative_net() -> None:
    entries = [
        GlRow(date(2025, 6, 1), Decimal("5"), "4000", "guv", "1"),
        GlRow(date(2025, 12, 31), Decimal("10"), "4000", "guv", "2"),
    ]
    trial = [
        TrialRow(
            "4000",
            "Erloese",
            "Posting",
            Decimal("10"),
            Decimal("0"),
            Decimal("15"),
            Decimal("0"),
            "2025-12-31",
        )
    ]
    accounts = {"4000": AccountInfo("4000", "Erloese", "Einnahmen", "", "Income")}
    compared = compare_trial(entries, trial, accounts, date(2025, 12, 31))
    assert compared.balance_zero == 1
    assert compared.change_zero == 0
    assert compared.day_zero == 1
    assert compared.posting_diffs[0].diff_balance == Decimal(0)
    assert compared.posting_diffs[0].diff_change == Decimal("-5")


def test_dynamic_route_wins_a_coverage_tie() -> None:
    shared = dict(
        works=True,
        per_entry=True,
        complete=True,
        http_status=200,
        seconds=1.0,
        rows=4,
        population=4,
        with_department=3,
        with_customer_group=1,
        detail="",
    )
    key, text = recommend(
        [
            RouteAssessment(key="expand", **shared),
            RouteAssessment(key="dynamic", **shared),
        ]
    )
    assert key == "dynamic"
    assert "dynamicDimensions" in text
    assert "\u2013" not in text


def test_metadata_lists_key_type_and_navigation() -> None:
    model = parse_metadata(METADATA)
    entity = model.entities["generalLedgerEntries"]
    assert entity.keys == ("id",)
    amount = next(field for field in entity.fields if field.name == "amount")
    assert amount.type_name.startswith("Edm.Decimal")
    assert amount.nullable == "ja"
    assert entity.navigation[0].name == "dimensionSetLines"
    text = render_feldinventar(
        [("v2.0", "generalLedgerEntries", "id")],
        {"v2.0": model},
        date(2026, 10, 24),
    )
    assert "Income Statement" in text
    assert "dimensionSetLines" in text
    assert "\u2013" not in text and "\u2014" not in text


def test_profile_describes_credit_balance_without_a_dash() -> None:
    rows = [
        GlRow(date(2026, 1, 15), Decimal("-8"), "4000", "guv", "1"),
        GlRow(date(2026, 1, 15), Decimal("2"), "5000", "guv", "2"),
        GlRow(date(2026, 1, 15), Decimal("6"), "1200", "bilanz", "3"),
    ]
    accounts = [
        AccountInfo("4000", "Waren", "Wareneinsatz", "Material", "Cost of Goods Sold"),
        AccountInfo("5000", "Erlöse", "Einnahmen", "Umsatz", "Income"),
        AccountInfo("0210", "Sonder\u2013konto", "", "", ""),
    ]
    profile = build_profile(
        stand=date(2026, 10, 24),
        as_of=date(2026, 9, 30),
        run_day=date(2026, 10, 24),
        gl_rows=rows,
        accounts=accounts,
        customers=open_at([], date(2026, 9, 30)),
        vendors=open_at([], date(2026, 9, 30)),
        routes=(),
        masters=(DimensionMaster("ABTEILUNG", "Abteilung", 1, ()),),
        department_values=("VERKAUF Verkauf",),
        customer_group_values=(),
        join=None,
        set_ids=_empty_sets(),
        filter_probes=(),
        shortcuts=(),
        trials=(),
        trial_error="",
        budget_rows=0,
        budget_entry_rows=0,
        closing_rows=0,
        sign=sign_check([("1", Decimal("-8"))], [("1", Decimal("0"), Decimal("8"))]),
        category_source="dem Feld category der API v2.0 accounts",
        dimension_entity_sets=(),
    )
    text = render_profile(profile)
    assert "Wareneinsatz" in text
    assert "Haben" in text
    assert "0210" in text
    assert "Sonder / konto" in text
    assert "\u2013" not in text and "\u2014" not in text
    assert "ABTEILUNG" in text
    assert "\u2013" not in text and "\u2014" not in text
    assert any("Wareneinsatz" in item for item in profile.findings_diff)


def test_accounts_without_category_keep_number_name_and_sum() -> None:
    accounts = [AccountInfo("0210", "Sonderkonto", "", "", "")]
    totals = {"0210": Decimal("15.5"), "9999": Decimal("2")}
    rows = accounts_without_category(accounts, totals)
    assert [(row.number, row.name, row.total) for row in rows] == [
        ("0210", "Sonderkonto", Decimal("15.5")),
        ("9999", "", Decimal("2")),
    ]


def test_snapshot_sample_has_at_most_100_rows(tmp_path: Path) -> None:
    rows = [{"number": str(index), "amount": Decimal("1.50")} for index in range(120)]
    written = write_snapshot_table(tmp_path, "accounts", rows, ["number", "amount"])
    assert written["rows"] == 120
    lines = (tmp_path / "accounts.sample.csv").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 101


def test_manifest_rejects_a_company_id(tmp_path: Path) -> None:
    company = "11111111-2222-3333-4444-555555555555"
    with pytest.raises(RuntimeError):
        write_manifest(tmp_path, {"note": company}, [company])


def test_secret_scan_rejects_bearer_text() -> None:
    with pytest.raises(RuntimeError):
        assert_no_secrets("Authorization: Bearer abc", [])


def _empty_sets():
    from src.datenbestand import SetIdStats

    return SetIdStats(0, 0, 0, 0, 0, 0)
