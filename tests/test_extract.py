"""Extractor plan and snapshot hygiene. No network."""

from __future__ import annotations

from pathlib import Path

from src.datenbestand import write_snapshot_table
from src.extract import entity_plan
from src.inventory import ROUTE_ANALYTICS, ROUTE_V2, load_entity_catalog
from src.trial_balance import sanitize_record


def test_plan_skips_dimension_set_entries_and_adds_dynamic_dimensions() -> None:
    catalog = load_entity_catalog()
    plan = entity_plan(catalog)
    names = [(item.route, item.entity_set) for item in plan]
    assert (ROUTE_ANALYTICS, "dimensionSetEntries") not in names
    assert (ROUTE_ANALYTICS, "dynamicDimensions") in names
    assert "dimensionSetLines" not in {name for _route, name in names}
    assert names.count((ROUTE_V2, "trialBalances")) == 1
    for route, entities in catalog.items():
        for entity in entities:
            key = (route, entity.entity_set)
            if key == (ROUTE_ANALYTICS, "dimensionSetEntries"):
                continue
            assert key in names


def test_snapshot_table_drops_service_urls(tmp_path: Path) -> None:
    rows = [
        sanitize_record(
            {
                "number": "1",
                "@odata.etag": "W/abc",
                "@odata.context": "https://api.businesscentral.dynamics.com/v2.0/tenant/api",
                "note": "https://login.microsoftonline.com/tenant",
            }
        )
    ]
    write_snapshot_table(tmp_path, "accounts", rows, ["number", "note"])
    blob = (tmp_path / "accounts.parquet").read_bytes()
    blob += (tmp_path / "accounts.sample.csv").read_bytes()
    assert b"businesscentral.dynamics.com" not in blob
    assert b"login.microsoftonline.com" not in blob
    assert b"@odata.context" not in blob
    assert b"@odata.etag" not in blob
