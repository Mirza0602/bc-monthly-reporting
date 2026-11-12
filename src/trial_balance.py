"""Trial balance load, amount parser, and the AP-02 plausibility checks.

The cutoff is not a filter on ledger entries. It selects the last reporting
month. Each month is read with a date range, because a single dateFilter
returns only that day's movement. totalDebit and totalCredit are the movement
inside the month. balanceAtDateDebit and balanceAtDateCredit are the ending
balance. Business Central echoes only the end date, so the snapshot also
stores periodStart and periodEnd. The year anchor is the full calendar year
before the first month, in the same table.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.bc_client import BusinessCentralClient
from src.datenbestand import cents, is_posting_type, norm_key, parse_amount, parse_iso_date
from src.inventory import ROUTE_V2

REPORTING_MONTHS = 13
TRIAL_EXTRA = ("periodStart", "periodEnd")
_URL_MARKERS = (
    "businesscentral.dynamics.com",
    "login.microsoftonline.com",
    "@odata.",
)


@dataclass(frozen=True)
class TrialAmount:
    account: str
    account_type: str
    name: str
    total_debit: Decimal
    total_credit: Decimal
    balance_debit: Decimal
    balance_credit: Decimal

    @property
    def movement(self) -> Decimal:
        return self.total_debit - self.total_credit

    @property
    def balance(self) -> Decimal:
        return self.balance_debit - self.balance_credit


@dataclass(frozen=True)
class MovementDiff:
    """Month movement against the change in ending balance."""

    account: str
    period_end: date
    movement: Decimal
    balance_delta: Decimal

    @property
    def difference(self) -> Decimal:
        return self.movement - self.balance_delta


@dataclass(frozen=True)
class BalanceDiff:
    """Ending balance against the ledger net through the cutoff."""

    account: str
    ending: Decimal
    cumulative: Decimal

    @property
    def difference(self) -> Decimal:
        return self.ending - self.cumulative


@dataclass(frozen=True)
class SideGap:
    period_end: date
    movement_gap: Decimal
    balance_gap: Decimal


@dataclass(frozen=True)
class CheckResult:
    as_of: date
    p1: Decimal
    income_rows: int
    balance_rows: int
    v2_rows: int
    population_gap: int
    movement: tuple[MovementDiff, ...]
    balance: tuple[BalanceDiff, ...]
    side_gaps: tuple[SideGap, ...]

    @property
    def failed(self) -> bool:
        sides = any(gap.movement_gap != 0 or gap.balance_gap != 0 for gap in self.side_gaps)
        unbalanced = bool(self.movement or self.balance)
        return self.p1 != 0 or self.population_gap != 0 or sides or unbalanced


def month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def reporting_periods(
    as_of: date,
    periods: int = REPORTING_MONTHS,
) -> tuple[tuple[date, date], ...]:
    """The last `periods` months through as_of, plus the month before the oldest."""
    if periods < 1:
        raise ValueError("periods must be at least 1.")
    spans: list[tuple[date, date]] = []
    year, month = as_of.year, as_of.month
    current_end = as_of
    for _ in range(periods + 1):
        spans.append((date(year, month, 1), current_end))
        year, month = shift_month(year, month, -1)
        current_end = month_end(year, month)
    spans.reverse()
    return tuple(spans)


def year_anchor_period(as_of: date) -> tuple[date, date] | None:
    """Calendar year that ends on 31.12. before the first reporting month.

    YTD is an ending balance minus 31.12. of the prior year. The month window
    does not contain that date when it starts after January, so the full year
    is loaded as one extra range in the same trial-balance table.
    """
    first_start = reporting_periods(as_of)[0][0]
    anchor_year = first_start.year - 1
    end = date(anchor_year, 12, 31)
    if any(period_end == end for _start, period_end in reporting_periods(as_of)):
        return None
    return date(anchor_year, 1, 1), end


def load_periods(as_of: date) -> tuple[tuple[date, date], ...]:
    """Month ranges plus the year anchor, anchor first."""
    months = reporting_periods(as_of)
    anchor = year_anchor_period(as_of)
    if anchor is None:
        return months
    return (anchor, *months)


def is_calendar_month(start: date, end: date) -> bool:
    """True when the range is one calendar month, not the year anchor."""
    return start == date(end.year, end.month, 1) and end == month_end(end.year, end.month)


def next_month_end(day: date) -> date:
    year, month = shift_month(day.year, day.month, 1)
    return month_end(year, month)


def period_filter(start: date, end: date) -> str:
    """Movement from month start through month end.

    dateFilter eq a single day returns that day's movement. ge/le returns the
    month. The service still echoes only the end date in the dateFilter field.
    """
    return f"dateFilter ge {start.isoformat()} and dateFilter le {end.isoformat()}"


def trial_columns(select: Sequence[str]) -> tuple[str, ...]:
    return tuple(select) + TRIAL_EXTRA


def money(value: Decimal) -> str:
    return f"{cents(value):.2f}"


def sanitize_record(row: Mapping[str, Any]) -> dict[str, Any]:
    """Drop OData control fields and values that carry a service URL."""
    cleaned: dict[str, Any] = {}
    for key, value in row.items():
        if not isinstance(key, str) or key.startswith("@"):
            continue
        if isinstance(value, str) and _has_service_url(value):
            continue
        if isinstance(value, (dict, list)):
            continue
        cleaned[key] = value
    return cleaned


def parse_trial_row(row: Mapping[str, Any]) -> TrialAmount:
    return TrialAmount(
        account=str(row.get("number") or "").strip(),
        account_type=str(row.get("accountType") or "").strip(),
        name=str(row.get("display") or "").strip(),
        total_debit=parse_amount(row.get("totalDebit")),
        total_credit=parse_amount(row.get("totalCredit")),
        balance_debit=parse_amount(row.get("balanceAtDateDebit")),
        balance_credit=parse_amount(row.get("balanceAtDateCredit")),
    )


def snapshot_rows(
    raw_rows: Sequence[Mapping[str, Any]],
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    """One snapshot row per account, with parsed amounts and the requested range."""
    prepared: list[dict[str, Any]] = []
    for raw in raw_rows:
        row = sanitize_record(raw)
        parsed = parse_trial_row(row)
        row["number"] = parsed.account
        row["accountType"] = parsed.account_type
        row["display"] = parsed.name
        row["totalDebit"] = cents(parsed.total_debit)
        row["totalCredit"] = cents(parsed.total_credit)
        row["balanceAtDateDebit"] = cents(parsed.balance_debit)
        row["balanceAtDateCredit"] = cents(parsed.balance_credit)
        row["periodStart"] = start.isoformat()
        row["periodEnd"] = end.isoformat()
        prepared.append(row)
    prepared.sort(key=lambda item: (str(item.get("periodEnd")), str(item.get("number"))))
    return prepared


def fetch_periods(
    client: BusinessCentralClient,
    company_id: str,
    as_of: date,
    columns: Sequence[str],
) -> tuple[list[dict[str, Any]], float, str]:
    """GET trialBalances once per month. The cutoff does not drop ledger rows."""
    fetched_at = _now()
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    select = [column for column in columns if column not in TRIAL_EXTRA]
    for start, end in load_periods(as_of):
        raw = client.get_collection(
            ROUTE_V2,
            "trialBalances",
            select=select,
            odata_filter=period_filter(start, end),
            company_id=company_id,
            parse_decimal=True,
        )
        rows.extend(snapshot_rows(raw, start, end))
        print(f"trialBalances {start.isoformat()}..{end.isoformat()}: {len(raw)} rows", flush=True)
    rows.sort(key=lambda item: (str(item.get("periodEnd")), str(item.get("number"))))
    return rows, round(time.perf_counter() - started, 3), fetched_at


def gl_p1(rows: Sequence[Mapping[str, Any]]) -> Decimal:
    """P1: total debit minus total credit over every general-ledger entry."""
    debit = Decimal(0)
    credit = Decimal(0)
    for row in rows:
        debit += parse_amount(row.get("debitAmount"))
        credit += parse_amount(row.get("creditAmount"))
    return cents(debit - credit)


def population_gap(income_rows: int, balance_rows: int, v2_rows: int) -> int:
    """Income-statement rows plus balance-sheet rows, minus the v2.0 ledger rows."""
    return income_rows + balance_rows - v2_rows


def cumulative_net(rows: Sequence[Mapping[str, Any]], as_of: date) -> dict[str, Decimal]:
    """Net debit minus credit by account for posting dates on or before as_of."""
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for row in rows:
        posted = parse_iso_date(row.get("postingDate"))
        if posted is None or posted > as_of:
            continue
        account = norm_key(row.get("accountNumber"))
        if not account:
            continue
        debit = parse_amount(row.get("debitAmount"))
        credit = parse_amount(row.get("creditAmount"))
        totals[account] += debit - credit
    return dict(totals)


def movement_diffs(rows: Sequence[Mapping[str, Any]]) -> list[MovementDiff]:
    """Posting accounts where the month movement is not the change in ending balance.

    Only a calendar month and the immediately previous month end are compared.
    The oldest month has no prior ending balance in this extract. The year
    anchor is not the previous month of the first reporting month, so it is
    not used as that opening balance.
    """
    grouped: dict[date, dict[str, TrialAmount]] = {}
    for row in rows:
        end = parse_iso_date(row.get("periodEnd"))
        if end is None:
            continue
        amount = parse_trial_row(row)
        if not amount.account or not is_posting_type(amount.account_type):
            continue
        grouped.setdefault(end, {})[amount.account] = amount
    dates = sorted(grouped)
    diffs: list[MovementDiff] = []
    for earlier, later in zip(dates, dates[1:], strict=False):
        if next_month_end(earlier) != later:
            continue
        previous = grouped[earlier]
        current = grouped[later]
        for account in sorted(set(previous) | set(current)):
            before = previous.get(account)
            after = current.get(account)
            opening = before.balance if before is not None else Decimal(0)
            movement = after.movement if after is not None else Decimal(0)
            closing = after.balance if after is not None else Decimal(0)
            delta = closing - opening
            if cents(movement - delta) != 0:
                diffs.append(MovementDiff(account, later, movement, delta))
    return diffs


def balance_diffs(
    trial_rows: Sequence[Mapping[str, Any]],
    gl_rows: Sequence[Mapping[str, Any]],
    as_of: date,
) -> list[BalanceDiff]:
    """Posting accounts where the ending balance differs from the ledger net."""
    current: list[TrialAmount] = []
    for row in trial_rows:
        if parse_iso_date(row.get("periodEnd")) != as_of:
            continue
        amount = parse_trial_row(row)
        if amount.account and is_posting_type(amount.account_type):
            current.append(amount)
    posted = cumulative_net(gl_rows, as_of)
    diffs: list[BalanceDiff] = []
    seen: set[str] = set()
    for amount in current:
        seen.add(amount.account)
        ledger = posted.get(amount.account, Decimal(0))
        if cents(amount.balance - ledger) != 0:
            diffs.append(BalanceDiff(amount.account, amount.balance, ledger))
    for account in sorted(posted):
        if account in seen or cents(posted[account]) == 0:
            continue
        diffs.append(BalanceDiff(account, Decimal(0), posted[account]))
    return diffs


def trial_side_gaps(rows: Sequence[Mapping[str, Any]]) -> list[SideGap]:
    """Debit minus credit on posting accounts, for the month and for the ending balance."""
    buckets: dict[date, list[Decimal]] = {}
    for row in rows:
        end = parse_iso_date(row.get("periodEnd"))
        if end is None:
            continue
        amount = parse_trial_row(row)
        if not is_posting_type(amount.account_type):
            continue
        slot = buckets.setdefault(end, [Decimal(0), Decimal(0), Decimal(0), Decimal(0)])
        slot[0] += amount.total_debit
        slot[1] += amount.total_credit
        slot[2] += amount.balance_debit
        slot[3] += amount.balance_credit
    gaps: list[SideGap] = []
    for end in sorted(buckets):
        debit, credit, balance_debit, balance_credit = buckets[end]
        gaps.append(SideGap(end, cents(debit - credit), cents(balance_debit - balance_credit)))
    return gaps


def movement_dict(item: MovementDiff) -> dict[str, str]:
    return {
        "account": item.account,
        "periodEnd": item.period_end.isoformat(),
        "movement": money(item.movement),
        "balanceDelta": money(item.balance_delta),
        "difference": money(item.difference),
    }


def balance_dict(item: BalanceDiff) -> dict[str, str]:
    return {
        "account": item.account,
        "ending": money(item.ending),
        "cumulative": money(item.cumulative),
        "difference": money(item.difference),
    }


def checks_document(result: CheckResult) -> dict[str, Any]:
    return {
        "p1": money(result.p1),
        "incomeStatementRows": result.income_rows,
        "balanceSheetRows": result.balance_rows,
        "generalLedgerEntriesRows": result.v2_rows,
        "populationGap": result.population_gap,
        "movementDiffs": [movement_dict(item) for item in result.movement],
        "balanceDiffs": [balance_dict(item) for item in result.balance],
        "trialSideGaps": [
            {
                "periodEnd": gap.period_end.isoformat(),
                "movementGap": money(gap.movement_gap),
                "balanceGap": money(gap.balance_gap),
            }
            for gap in result.side_gaps
        ],
    }


def build_checks(
    *,
    as_of: date,
    gl_rows: Sequence[Mapping[str, Any]],
    income_rows: int,
    balance_rows: int,
    trial_rows: Sequence[Mapping[str, Any]],
) -> CheckResult:
    return CheckResult(
        as_of=as_of,
        p1=gl_p1(gl_rows),
        income_rows=income_rows,
        balance_rows=balance_rows,
        v2_rows=len(gl_rows),
        population_gap=population_gap(income_rows, balance_rows, len(gl_rows)),
        movement=tuple(movement_diffs(trial_rows)),
        balance=tuple(balance_diffs(trial_rows, gl_rows, as_of)),
        side_gaps=tuple(trial_side_gaps(trial_rows)),
    )


def latest_snapshot(root: Path | None = None) -> Path | None:
    folder = root or Path(__file__).resolve().parents[1] / "data" / "snapshots"
    if not folder.exists():
        return None
    candidates = sorted(
        path for path in folder.iterdir() if path.is_dir() and (path / "manifest.json").is_file()
    )
    return candidates[-1] if candidates else None


def evaluate_snapshot(folder: Path) -> CheckResult:
    """Run the checks on a snapshot folder. No network."""
    manifest = json.loads(folder.joinpath("manifest.json").read_text(encoding="utf-8"))
    as_of = date.fromisoformat(str(manifest["stichtag"]))
    gl_rows = _records(folder, manifest, "generalLedgerEntries")
    income_rows = len(_records(folder, manifest, "incomeStatementGeneralLedgerEntries"))
    balance_rows = len(_records(folder, manifest, "balanceSheetGeneralLedgerEntries"))
    trial_rows = _records(folder, manifest, "trialBalances")
    return build_checks(
        as_of=as_of,
        gl_rows=gl_rows,
        income_rows=income_rows,
        balance_rows=balance_rows,
        trial_rows=trial_rows,
    )


def period_present(rows: Sequence[Mapping[str, Any]], start: date, end: date) -> bool:
    start_text = start.isoformat()
    end_text = end.isoformat()
    return any(
        str(row.get("periodStart") or "")[:10] == start_text
        and str(row.get("periodEnd") or "")[:10] == end_text
        for row in rows
    )


def replace_period(
    rows: Sequence[Mapping[str, Any]],
    start: date,
    end: date,
    fresh: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Drop one date range and append the fresh rows. Other ranges stay."""
    start_text = start.isoformat()
    end_text = end.isoformat()
    merged = [
        dict(row)
        for row in rows
        if not (
            str(row.get("periodStart") or "")[:10] == start_text
            and str(row.get("periodEnd") or "")[:10] == end_text
        )
    ]
    merged.extend(dict(row) for row in fresh)
    merged.sort(key=lambda item: (str(item.get("periodEnd")), str(item.get("number"))))
    return merged


def fetch_year_anchor(folder: Path) -> int:
    """GET the year anchor and merge it into the snapshot. Other entities stay."""
    from src.bc_client import BusinessCentralClient, BusinessCentralError
    from src.datenbestand import scan_tree
    from src.inventory import (
        ROUTE_V2,
        CatalogError,
        ConfigurationError,
        load_entity_catalog,
        read_company_id,
    )

    manifest = json.loads(folder.joinpath("manifest.json").read_text(encoding="utf-8"))
    as_of = date.fromisoformat(str(manifest["stichtag"]))
    anchor = year_anchor_period(as_of)
    if anchor is None:
        print("The month window already contains the prior year end.")
        return 0
    start, end = anchor
    try:
        catalog = load_entity_catalog()
        client = BusinessCentralClient.from_env()
        company_id = read_company_id()
    except (OSError, CatalogError, ConfigurationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    client.company = company_id
    needles = _secret_needles(client, company_id)
    try:
        company = _company_name(client, company_id)
    except BusinessCentralError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    trial = _trial_entity(catalog)
    columns = list(trial_columns(trial.select))
    existing = _records(folder, manifest, "trialBalances")
    fetched_at = manifest_anchor_time(manifest)
    seconds = 0.0
    if period_present(existing, start, end):
        print(f"Year anchor {start.isoformat()}..{end.isoformat()} is already in the snapshot.")
        rows = existing
    else:
        started = time.perf_counter()
        try:
            raw = client.get_collection(
                ROUTE_V2,
                "trialBalances",
                select=[column for column in columns if column not in TRIAL_EXTRA],
                odata_filter=period_filter(start, end),
                company_id=company_id,
                parse_decimal=True,
            )
        except BusinessCentralError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        seconds = round(time.perf_counter() - started, 3)
        fresh = snapshot_rows(raw, start, end)
        rows = replace_period(existing, start, end, fresh)
        fetched_at = _now()
        print(
            f"trialBalances {start.isoformat()}..{end.isoformat()}: {len(fresh)} rows",
            flush=True,
        )
    try:
        _write_anchor(
            folder,
            manifest,
            rows,
            columns,
            start,
            end,
            company,
            fetched_at,
            seconds,
            needles,
        )
        scan_tree(folder, needles)
    except (OSError, RuntimeError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    result = evaluate_snapshot(folder)
    _print_checks(result)
    print(f"Year anchor {end.isoformat()} stored. Company name only, no id.")
    return 1 if result.failed else 0


def _secret_needles(client: Any, company_id: str) -> tuple[str, ...]:
    values = (client.tenant_id, client.client_id, client._client_secret, company_id)
    return tuple(dict.fromkeys(value for value in values if value))


def _company_name(client: Any, company_id: str) -> str:
    from src.bc_client import _GUID, BusinessCentralError
    from src.inventory import ROUTE_V2

    for row in client.list_companies(ROUTE_V2):
        if str(row.get("id") or "") != company_id:
            continue
        name = str(row.get("displayName") or row.get("name") or "").strip()
        if name and not _GUID.match(name):
            return name
        break
    raise BusinessCentralError("The company name could not be read.")


def _trial_entity(catalog: Mapping[str, Any]) -> Any:
    from src.inventory import ROUTE_V2

    for entity in catalog[ROUTE_V2]:
        if entity.entity_set == "trialBalances":
            return entity
    raise KeyError("trialBalances")


def _write_anchor(
    folder: Path,
    manifest: dict[str, Any],
    rows: Sequence[Mapping[str, Any]],
    columns: Sequence[str],
    start: date,
    end: date,
    company: str,
    fetched_at: str,
    seconds: float,
    needles: Sequence[str],
) -> None:
    from src.datenbestand import write_manifest, write_snapshot_table

    written = write_snapshot_table(folder, "v2__trialBalances", rows, columns)
    as_of = date.fromisoformat(str(manifest["stichtag"]))
    periods = load_periods(as_of)
    anchor_rows = sum(
        1
        for row in rows
        if str(row.get("periodStart") or "")[:10] == start.isoformat()
        and str(row.get("periodEnd") or "")[:10] == end.isoformat()
    )
    previous = manifest.get("yearAnchor")
    anchor_doc = {
        "periodStart": start.isoformat(),
        "periodEnd": end.isoformat(),
        "fetchedAt": fetched_at,
        "seconds": seconds,
        "rows": anchor_rows,
    }
    if seconds == 0 and isinstance(previous, dict):
        anchor_doc["fetchedAt"] = str(previous.get("fetchedAt") or fetched_at)
        anchor_doc["seconds"] = previous.get("seconds", 0)
    for item in manifest["entities"]:
        if item.get("entity") == "trialBalances":
            item["rows"] = written["rows"]
            item["parquet"] = written["parquet"]
            item["csvSample"] = written["csvSample"]
            item["periods"] = len(periods)
            item["periodStart"] = periods[0][0].isoformat()
            item["periodEnd"] = periods[-1][1].isoformat()
    manifest["company"] = company
    manifest["yearAnchor"] = anchor_doc
    manifest["checks"] = checks_document(evaluate_snapshot(folder))
    write_manifest(folder, manifest, needles)


def manifest_anchor_time(manifest: Mapping[str, Any]) -> str:
    anchor = manifest.get("yearAnchor")
    if isinstance(anchor, dict) and anchor.get("fetchedAt"):
        return str(anchor["fetchedAt"])
    return _now()


def main(argv: list[str] | None = None) -> int:
    """Print the checks for a snapshot. --fetch-anchor reads one trial-balance range."""
    parser = argparse.ArgumentParser(
        description="Print trial-balance checks for a snapshot, or load the year anchor."
    )
    parser.add_argument(
        "--snapshot",
        default=None,
        help="Snapshot folder. Default: the latest folder under data/snapshots.",
    )
    parser.add_argument(
        "--fetch-anchor",
        action="store_true",
        help="Load the year-end anchor into the snapshot. Does not reload other entities.",
    )
    args = parser.parse_args(argv)
    _configure_stdio()
    folder = Path(args.snapshot) if args.snapshot else latest_snapshot()
    if folder is None or not folder.joinpath("manifest.json").is_file():
        print("ERROR: No snapshot. Run python -m src.extract.", file=sys.stderr)
        return 1
    if args.fetch_anchor:
        return fetch_year_anchor(folder)
    try:
        result = evaluate_snapshot(folder)
    except (OSError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    _print_checks(result)
    return 1 if result.failed else 0


def _print_checks(result: CheckResult) -> None:
    print(f"P1 {money(result.p1)}.")
    print(
        "GL rows "
        f"income {result.income_rows}, balance {result.balance_rows}, "
        f"v2 {result.v2_rows}, gap {result.population_gap}."
    )
    print(f"Movement diffs {len(result.movement)}.")
    for item in result.movement[:50]:
        print(
            f"movement {item.account} {item.period_end.isoformat()} "
            f"{money(item.difference)}"
        )
    print(f"Balance diffs {len(result.balance)}.")
    for item in result.balance[:50]:
        print(f"balance {item.account} {money(item.difference)}")
    for gap in result.side_gaps:
        if gap.movement_gap != 0 or gap.balance_gap != 0:
            print(
                f"Soll/Haben {gap.period_end.isoformat()} "
                f"movement {money(gap.movement_gap)} balance {money(gap.balance_gap)}."
            )


def _records(folder: Path, manifest: Mapping[str, Any], entity: str) -> list[dict[str, Any]]:
    import pandas as pd

    for item in manifest.get("entities", ()):
        if isinstance(item, dict) and item.get("entity") == entity:
            frame = pd.read_parquet(folder / str(item["parquet"]))
            return frame.to_dict(orient="records")
    raise KeyError(entity)


def _has_service_url(value: str) -> bool:
    lowered = value.casefold()
    return any(marker in lowered for marker in _URL_MARKERS)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


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
