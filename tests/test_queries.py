"""Power Query templates: file, header, and no GUID in the query text.

fnBetrag follows parse_amount in src/datenbestand.py.
Same cases as tests/test_parser.py:
"72,893.84" -> 72893.84
"72.893,84" -> 72893.84
"(1.234,56)" -> -1234.56
"" -> 0
None -> 0
"  " -> 0
Both separators: the rightmost one is the decimal mark.
One comma and exactly three digits after it, with digits before it, is a thousands comma.
Parentheses, a leading minus, or a trailing minus make the amount negative.
Empty text is 0.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

GUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
DATE = re.compile(r"#date\((\d+), (\d+), (\d+)\)")
HEADER_WORDS = ("Quelle", "Filter", "Schlüssel", "Zeilenzahl")
HELPERS = (
    "pUmgebung.pq",
    "pMandant.pq",
    "pStichtag.pq",
    "pRepoPfad.pq",
    "fnQuelle.pq",
    "fnBetrag.pq",
)
EXPECTED = (
    ("DimDatum", "generiert", "1461"),
    ("DimKonto", "microsoft/analytics/v1.0 generalLedgerAccounts", "221"),
    ("DimDimensionsSet", "microsoft/analytics/v1.0 dynamicDimensions", "37"),
    ("DimKunde", "microsoft/analytics/v1.0 customers", "5"),
    ("DimLieferant", "microsoft/analytics/v1.0 vendors", "8"),
    ("DimArtikel", "microsoft/analytics/v1.0 items", "80"),
    (
        "FactSachposten",
        "microsoft/analytics/v1.0 incomeStatementGeneralLedgerEntries"
        " und balanceSheetGeneralLedgerEntries",
        "4384",
    ),
    ("FactDebitorenposten", "microsoft/analytics/v1.0 customerLedgerEntries", "1145"),
    ("FactKreditorenposten", "microsoft/analytics/v1.0 vendorLedgerEntries", "869"),
    (
        "FactWertposten",
        "microsoft/analytics/v1.0 salesValueEntries und itemValueEntries",
        "878",
    ),
    ("FactSaldenliste", "v2.0 trialBalances", "3315"),
)
# DimArtikel, DimDimensionsSet and DimKonto still call Table.NestedJoin and loaded on 26.10.2026.
# FactSachposten.pq: der Join läuft gegen die mit Table.Buffer gepufferte
# Belegtabelle aus v2.0 generalLedgerEntries, also lokal.
LOADED_WITH_NESTED_JOIN = (
    "DimArtikel.pq",
    "DimDimensionsSet.pq",
    "DimKonto.pq",
    "FactSachposten.pq",
)
PERIODS = {
    ("2024-01-01", "2024-12-31"),
    ("2025-08-01", "2025-08-31"),
    ("2025-09-01", "2025-09-30"),
    ("2025-10-01", "2025-10-31"),
    ("2025-11-01", "2025-11-30"),
    ("2025-12-01", "2025-12-31"),
    ("2026-01-01", "2026-01-31"),
    ("2026-02-01", "2026-02-28"),
    ("2026-03-01", "2026-03-31"),
    ("2026-04-01", "2026-04-30"),
    ("2026-05-01", "2026-05-31"),
    ("2026-06-01", "2026-06-30"),
    ("2026-07-01", "2026-07-31"),
    ("2026-08-01", "2026-08-31"),
    ("2026-09-01", "2026-09-30"),
}


def _folder() -> Path:
    return Path(__file__).resolve().parents[1] / "powerbi" / "queries"


def _header(text: str) -> str:
    lines: list[str] = []
    started = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if started:
                break
            continue
        if stripped.startswith("//"):
            lines.append(stripped)
            started = True
            continue
        break
    return "\n".join(lines)


def _periods(text: str) -> set[tuple[str, str]]:
    found = DATE.findall(text)
    assert len(found) % 2 == 0
    days = [f"{year}-{int(month):02d}-{int(day):02d}" for year, month, day in found]
    return {(days[index], days[index + 1]) for index in range(0, len(days), 2)}


def test_helpers_and_no_budget_query() -> None:
    folder = _folder()
    for name in HELPERS:
        assert (folder / name).is_file()
    assert not (folder / "FactBudget.pq").exists()
    assert not (folder / "FactSaldenlisteOData.pq").exists()
    source = (folder / "fnQuelle.pq").read_text(encoding="utf-8")
    assert "Dynamics365BusinessCentral.ApiContentsWithOptions(null, null, null, null)" in source
    assert "Text.Upper(pUmgebung)" in source


def test_expected_queries_have_header_and_no_guid() -> None:
    folder = _folder()
    with (folder / "erwartete_zeilen.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [(row["abfrage"], row["quelle"], row["erwartet"]) for row in rows] == list(EXPECTED)
    for name, _source, count in EXPECTED:
        path = folder / f"{name}.pq"
        text = path.read_text(encoding="utf-8")
        assert GUID.search(text) is None
        header = _header(text)
        assert header
        for word in HEADER_WORDS:
            assert word in header
        assert count in header


def test_no_guid_or_long_dash_in_query_folder() -> None:
    folder = _folder()
    paths = list(folder.glob("*.pq")) + [
        folder / "README.md",
        folder / "erwartete_zeilen.csv",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert GUID.search(text) is None, path.name
        assert "\u2013" not in text and "\u2014" not in text, path.name


def test_trial_balance_periods_match_snapshot() -> None:
    folder = _folder()
    text = (folder / "FactSaldenliste.pq").read_text(encoding="utf-8")
    assert _periods(text) == PERIODS


def test_no_parameter_handoff_or_nested_join() -> None:
    folder = _folder()
    for path in sorted(folder.glob("*.pq")):
        text = path.read_text(encoding="utf-8")
        assert "ApiContentsWithOptions(pUmgebung" not in text, path.name
        code = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("//")
        )
        if path.name not in LOADED_WITH_NESTED_JOIN:
            assert "Table.NestedJoin" not in code, path.name
        if path.name == "FactSachposten.pq":
            assert re.search(r"(?m)^[ \t]*Belege\s*=\s*Table\.Buffer\b", code), path.name
