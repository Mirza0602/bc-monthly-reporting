"""Acceptance checks for the AP-02 snapshot. No identifiers are printed."""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pytest
from dotenv import load_dotenv

from src.extract import entity_plan
from src.inventory import load_entity_catalog
from src.trial_balance import evaluate_snapshot, latest_snapshot

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data" / "snapshots" / "2026-10-24"
_IDENTIFIER_KEYS = ("BC_TENANT_ID", "BC_CLIENT_ID", "BC_CLIENT_SECRET", "BC_COMPANY")


def test_snapshot_replaces_the_ap01_folder() -> None:
    folders = sorted(path.name for path in (ROOT / "data" / "snapshots").iterdir() if path.is_dir())
    assert folders == ["2026-10-24"]
    assert latest_snapshot() == SNAPSHOT


def test_manifest_lists_every_planned_entity() -> None:
    manifest = json.loads(SNAPSHOT.joinpath("manifest.json").read_text(encoding="utf-8"))
    assert manifest["stichtag"] == "2026-09-30"
    assert manifest["runDate"] == "2026-10-24"
    found = {(item["route"], item["entity"]) for item in manifest["entities"]}
    expected = {(item.route, item.entity_set) for item in entity_plan(load_entity_catalog())}
    assert found == expected
    for item in manifest["entities"]:
        assert item["rows"] >= 0
        assert item["fetchedAt"]
        assert "seconds" in item
        assert SNAPSHOT.joinpath(item["parquet"]).is_file()
        assert SNAPSHOT.joinpath(item["csvSample"]).is_file()
        assert "dimensionSetEntries" not in item["entity"]
    trial = next(item for item in manifest["entities"] if item["entity"] == "trialBalances")
    assert trial["periods"] == 15
    assert trial["rows"] == 3315
    assert trial["periodStart"] == "2024-01-01"
    assert trial["periodEnd"] == "2026-09-30"
    assert manifest["company"] == "CRONUS DE"
    assert manifest["yearAnchor"]["periodStart"] == "2024-01-01"
    assert manifest["yearAnchor"]["periodEnd"] == "2024-12-31"
    assert manifest["yearAnchor"]["rows"] == 221
    assert manifest["checks"]["p1"] == "0.00"
    assert manifest["checks"]["populationGap"] == 0
    assert manifest["checks"]["movementDiffs"] == []
    assert manifest["checks"]["balanceDiffs"] == []


def test_snapshot_keeps_entries_after_the_cutoff_and_balances() -> None:
    import pandas as pd

    manifest = json.loads(SNAPSHOT.joinpath("manifest.json").read_text(encoding="utf-8"))
    general = _frame(manifest, "generalLedgerEntries")
    income = _frame(manifest, "incomeStatementGeneralLedgerEntries")
    balance = _frame(manifest, "balanceSheetGeneralLedgerEntries")
    posted = pd.to_datetime(general["postingDate"])
    assert len(income) + len(balance) == len(general) == 4384
    assert int((posted > "2026-09-30").sum()) == 48
    assert posted.min() == pd.Timestamp("2024-01-01")
    assert posted.max() == pd.Timestamp("2027-09-01")
    result = evaluate_snapshot(SNAPSHOT)
    assert result.as_of == date(2026, 9, 30)
    assert result.p1 == 0
    assert result.population_gap == 0
    assert result.movement == ()
    assert result.balance == ()
    assert result.failed is False
    assert not list(SNAPSHOT.glob("*dimensionSetEntries*"))
    assert not list(SNAPSHOT.glob("*dimensionSetLines*"))
    dynamic = _frame(manifest, "dynamicDimensions")
    assert len(dynamic) > 0
    assert "dimensionSetID" in dynamic.columns


def test_samples_have_at_most_100_data_rows() -> None:
    for path in SNAPSHOT.glob("*.sample.csv"):
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 101


def test_snapshot_omits_service_urls_and_odata_context() -> None:
    offenders: list[str] = []
    for path in SNAPSHOT.rglob("*"):
        if not path.is_file():
            continue
        lowered = path.read_bytes().lower()
        if b"businesscentral.dynamics.com" in lowered or b"login.microsoftonline.com" in lowered:
            offenders.append(f"{path.name}: environment url")
        if b"@odata.context" in lowered or b"@odata.nextlink" in lowered:
            offenders.append(f"{path.name}: odata context")
    assert offenders == []


def test_snapshot_omits_configured_identifiers() -> None:
    needles = _configured_identifiers()
    if needles is None:
        pytest.skip("Keine .env vorhanden, Kennungsprüfung übersprungen")
    offenders: list[str] = []
    for path in SNAPSHOT.rglob("*"):
        if not path.is_file():
            continue
        blob = path.read_bytes()
        for index, needle in enumerate(needles):
            if needle in blob:
                offenders.append(f"{path.name}: configured identifier {index}")
    assert offenders == []


def _frame(manifest: dict, entity: str):
    import pandas as pd

    item = next(row for row in manifest["entities"] if row["entity"] == entity)
    return pd.read_parquet(SNAPSHOT / item["parquet"])


def _configured_identifiers() -> list[bytes] | None:
    env_file = ROOT / ".env"
    if not env_file.is_file():
        return None
    load_dotenv(env_file, override=False)
    found: list[bytes] = []
    for key in _IDENTIFIER_KEYS:
        raw = os.environ.get(key, "").strip()
        if len(raw) >= 8:
            found.append(raw.encode("utf-8"))
    local = ROOT / ".env.local"
    if local.is_file():
        for line in local.read_text(encoding="utf-8").splitlines():
            if line.startswith("BC_COMPANY="):
                raw = line.split("=", 1)[1].strip()
                if len(raw) >= 8:
                    found.append(raw.encode("utf-8"))
    unique = list(dict.fromkeys(found))
    if len(unique) < 4:
        raise AssertionError("Configured identifiers for the snapshot check are missing.")
    return unique
