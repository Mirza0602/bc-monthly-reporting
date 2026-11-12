"""Tests for config/entities.yaml."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.inventory import (
    ROUTE_ANALYTICS,
    ROUTE_V2,
    CatalogError,
    default_catalog_path,
    load_entity_catalog,
)

# route, entity set, key, filter field, number of documented columns
SPECS: tuple[tuple[str, str, str | None, str | None, int], ...] = (
    (ROUTE_V2, "generalLedgerEntries", "id", "postingDate", 13),
    (ROUTE_V2, "trialBalances", "accountId", "dateFilter", 9),
    (ROUTE_V2, "accounts", "id", None, 14),
    (ROUTE_V2, "dimensions", "id", None, 5),
    (ROUTE_V2, "dimensionValues", "id", None, 6),
    (ROUTE_V2, "customers", "id", None, 27),
    (ROUTE_V2, "vendors", "id", None, 22),
    (ROUTE_V2, "items", "id", None, 22),
    (ROUTE_V2, "itemCategories", "id", None, 4),
    (ROUTE_ANALYTICS, "incomeStatementGeneralLedgerEntries", "entryNo", "postingDate", 11),
    (ROUTE_ANALYTICS, "balanceSheetGeneralLedgerEntries", "entryNo", "postingDate", 11),
    (ROUTE_ANALYTICS, "closingGeneralLedgerEntries", "entryNo", "postingDate", 11),
    (ROUTE_ANALYTICS, "customerLedgerEntries", "dcleEntryNo", "dclePostingDate", 22),
    (ROUTE_ANALYTICS, "vendorLedgerEntries", "dvleEntryNo", "dvlePostingDate", 22),
    (ROUTE_ANALYTICS, "salesValueEntries", "entryNo", "postingDate", 20),
    (ROUTE_ANALYTICS, "purchaseValueEntries", "entryNo", "postingDate", 19),
    (ROUTE_ANALYTICS, "itemValueEntries", "entryNo", "postingDate", 14),
    (ROUTE_ANALYTICS, "itemLedgerEntries", "entryNo", "postingDate", 22),
    (ROUTE_ANALYTICS, "generalLedgerAccounts", "accountNo", None, 7),
    (ROUTE_ANALYTICS, "generalLedgerAccountCategories", "entryNo", None, 11),
    (ROUTE_ANALYTICS, "accountCategories", "powerBIAccCategory", None, 3),
    (ROUTE_ANALYTICS, "dimensions", None, None, 24),
    (ROUTE_ANALYTICS, "dimensionSetEntries", "dimensionSetID", None, 19),
    (ROUTE_ANALYTICS, "generalLedgerBudgets", "budgetName", None, 2),
    (ROUTE_ANALYTICS, "generalLedgerBudgetEntries", "entryNo", "budgetDate", 6),
    (ROUTE_ANALYTICS, "customers", "customerNo", None, 11),
    (ROUTE_ANALYTICS, "vendors", "vendorNo", None, 9),
    (ROUTE_ANALYTICS, "items", "itemNo", None, 23),
    (ROUTE_ANALYTICS, "itemCategories", "code", None, 4),
    (ROUTE_ANALYTICS, "salespersonPurchasers", "salespersonPurchaserCode", None, 2),
    (ROUTE_ANALYTICS, "locations", "locationCode", None, 3),
)

REQUIRED: dict[tuple[str, str], tuple[str, ...]] = {
    (ROUTE_V2, "generalLedgerEntries"): (
        "id",
        "entryNumber",
        "postingDate",
        "debitAmount",
        "creditAmount",
        "accountNumber",
    ),
    (ROUTE_V2, "trialBalances"): (
        "accountId",
        "number",
        "totalDebit",
        "totalCredit",
        "balanceAtDateDebit",
        "balanceAtDateCredit",
        "dateFilter",
    ),
    (ROUTE_V2, "accounts"): ("id", "number", "category", "subCategory", "accountType"),
    (ROUTE_ANALYTICS, "incomeStatementGeneralLedgerEntries"): (
        "entryNo",
        "accountNo",
        "postingDate",
        "amount",
        "dimensionSetID",
        "sourceType",
        "sourceNo",
        "sourceCode",
        "description",
    ),
    (ROUTE_ANALYTICS, "balanceSheetGeneralLedgerEntries"): (
        "entryNo",
        "glAccountNo",
        "postingDate",
        "amount",
        "dimensionSetID",
    ),
    (ROUTE_ANALYTICS, "closingGeneralLedgerEntries"): ("entryNo", "glAccountNo", "postingDate"),
    (ROUTE_ANALYTICS, "customerLedgerEntries"): (
        "dcleEntryNo",
        "dclePostingDate",
        "dcleAmountLCY",
        "dcleEntryType",
        "cleDueDate",
        "cleOpen",
        "dcleCustomerNo",
    ),
    (ROUTE_ANALYTICS, "vendorLedgerEntries"): (
        "dvleEntryNo",
        "dvlePostingDate",
        "dvleAmountLCY",
        "dvleVendorNo",
    ),
    (ROUTE_ANALYTICS, "salesValueEntries"): (
        "entryNo",
        "postingDate",
        "salesAmountActual",
        "costAmountActual",
        "customerNo",
        "itemNo",
    ),
    (ROUTE_ANALYTICS, "itemValueEntries"): (
        "entryNo",
        "postingDate",
        "costAmountActual",
        "costAmountExpected",
        "itemNo",
    ),
    (ROUTE_ANALYTICS, "dimensionSetEntries"): (
        "dimensionSetID",
        "dimension1ValueCode",
        "dimension8ValueName",
    ),
    (ROUTE_ANALYTICS, "generalLedgerBudgetEntries"): (
        "entryNo",
        "budgetDate",
        "budgetAmount",
        "glAccountNo",
        "budgetName",
    ),
}

_COLUMN = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_ALLOWED_FILTERS = {
    None,
    "postingDate",
    "dateFilter",
    "dclePostingDate",
    "dvlePostingDate",
    "budgetDate",
}


def test_catalog_matches_part_a2() -> None:
    catalog = load_entity_catalog()
    found = {
        (entity.route, entity.entity_set): entity
        for entities in catalog.values()
        for entity in entities
    }
    assert list(found) == [(route, name) for route, name, _key, _filt, _count in SPECS]
    for route, name, key, filter_field, count in SPECS:
        entity = found[(route, name)]
        assert entity.key == key
        assert entity.filter_field == filter_field
        assert entity.filter_field in _ALLOWED_FILTERS
        assert len(entity.select) == count, (route, name, len(entity.select), entity.select)
        assert len(set(entity.select)) == count
        assert all(_COLUMN.fullmatch(column) for column in entity.select)
        if key is not None:
            assert key in entity.select
        if filter_field is not None:
            assert filter_field in entity.select
        required = REQUIRED.get((route, name), ())
        assert set(required) <= set(entity.select)


def test_documented_account_field_names_stay_distinct() -> None:
    catalog = load_entity_catalog()
    by_name = {
        entity.entity_set: entity
        for entity in catalog[ROUTE_ANALYTICS]
    }
    income = by_name["incomeStatementGeneralLedgerEntries"]
    balance = by_name["balanceSheetGeneralLedgerEntries"]
    assert "accountNo" in income.select
    assert "glAccountNo" not in income.select
    assert "glAccountNo" in balance.select
    assert "accountNo" not in balance.select
    assert "baseUnitofMeasure" in by_name["items"].select
    assert "open" in by_name["itemLedgerEntries"].select


def test_only_shortcut_dimensions_have_no_key() -> None:
    catalog = load_entity_catalog()
    missing = [
        (entity.route, entity.entity_set)
        for entities in catalog.values()
        for entity in entities
        if entity.key is None
    ]
    assert missing == [(ROUTE_ANALYTICS, "dimensions")]


def test_deprecated_finance_reports_api_is_absent() -> None:
    text = default_catalog_path().read_text(encoding="utf-8")
    assert "reportsFinance" not in text
    assert "beta" not in text.lower()


def test_duplicate_entity_set_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "entities.yaml"
    path.write_text(
        """
v2.0:
  - entity_set: accounts
    select:
      - id
    filter_field: null
    key: id
  - entity_set: accounts
    select:
      - id
    filter_field: null
    key: id
"microsoft/analytics/v1.0":
  - entity_set: customers
    select:
      - customerNo
    filter_field: null
    key: customerNo
""",
        encoding="utf-8",
    )
    with pytest.raises(CatalogError, match="Duplicate"):
        load_entity_catalog(path)
