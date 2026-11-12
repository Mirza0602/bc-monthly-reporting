"""Trial-balance periods and the AP-02 checks. No network."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.trial_balance import (
    balance_diffs,
    gl_p1,
    load_periods,
    month_end,
    movement_diffs,
    period_filter,
    population_gap,
    replace_period,
    reporting_periods,
    snapshot_rows,
    trial_side_gaps,
    year_anchor_period,
)


def test_reporting_months_include_one_prior_month_end() -> None:
    periods = reporting_periods(date(2026, 9, 30))
    ends = [end for _start, end in periods]
    assert ends == [
        date(2025, 8, 31),
        date(2025, 9, 30),
        date(2025, 10, 31),
        date(2025, 11, 30),
        date(2025, 12, 31),
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
        date(2026, 4, 30),
        date(2026, 5, 31),
        date(2026, 6, 30),
        date(2026, 7, 31),
        date(2026, 8, 31),
        date(2026, 9, 30),
    ]
    assert periods[0] == (date(2025, 8, 1), date(2025, 8, 31))
    assert periods[-1] == (date(2026, 9, 1), date(2026, 9, 30))
    assert len(ends) == 14


def test_year_anchor_precedes_the_month_window() -> None:
    assert year_anchor_period(date(2026, 9, 30)) == (date(2024, 1, 1), date(2024, 12, 31))
    periods = load_periods(date(2026, 9, 30))
    assert periods[0] == (date(2024, 1, 1), date(2024, 12, 31))
    assert periods[1] == (date(2025, 8, 1), date(2025, 8, 31))
    assert periods[-1] == (date(2026, 9, 1), date(2026, 9, 30))
    assert len(periods) == 15


def test_movement_skips_a_gap_before_the_first_month() -> None:
    rows = [
        _trial("1000", "Posting", "0", "0", "10", "0", date(2024, 12, 31)),
        _trial("1000", "Posting", "1", "0", "50", "0", date(2025, 8, 31)),
        _trial("1000", "Posting", "5", "0", "55", "0", date(2025, 9, 30)),
    ]
    assert movement_diffs(rows) == []


def test_replace_period_keeps_other_months() -> None:
    month = _trial("1000", "Posting", "1", "0", "1", "0", date(2026, 8, 31))
    old_anchor = _trial("1000", "Posting", "9", "0", "9", "0", date(2024, 12, 31))
    old_anchor["periodStart"] = "2024-01-01"
    fresh = _trial("1000", "Posting", "2", "0", "2", "0", date(2024, 12, 31))
    fresh["periodStart"] = "2024-01-01"
    merged = replace_period([month, old_anchor], date(2024, 1, 1), date(2024, 12, 31), [fresh])
    assert len(merged) == 2
    assert merged[0]["periodEnd"] == "2024-12-31"
    assert merged[0]["periodStart"] == "2024-01-01"
    assert merged[0]["totalDebit"] == "2"
    assert merged[1]["periodEnd"] == "2026-08-31"


def test_month_end_handles_february() -> None:
    assert month_end(2024, 2) == date(2024, 2, 29)
    assert month_end(2025, 2) == date(2025, 2, 28)


def test_period_filter_is_a_month_range() -> None:
    assert period_filter(date(2026, 9, 1), date(2026, 9, 30)) == (
        "dateFilter ge 2026-09-01 and dateFilter le 2026-09-30"
    )


def test_snapshot_rows_parse_both_amount_formats_and_drop_odata() -> None:
    rows = snapshot_rows(
        [
            {
                "number": "1000",
                "accountType": "Posting",
                "display": "Sales",
                "totalDebit": "72,893.84",
                "totalCredit": "72.893,84",
                "balanceAtDateDebit": "1.00",
                "balanceAtDateCredit": "0.00",
                "dateFilter": "2026-09-30",
                "@odata.etag": "W/abc",
                "@odata.context": "https://api.businesscentral.dynamics.com/v2.0/x",
            }
        ],
        date(2026, 9, 1),
        date(2026, 9, 30),
    )
    assert rows[0]["totalDebit"] == Decimal("72893.84")
    assert rows[0]["totalCredit"] == Decimal("72893.84")
    assert rows[0]["periodStart"] == "2026-09-01"
    assert rows[0]["periodEnd"] == "2026-09-30"
    assert "@odata.etag" not in rows[0]
    assert "@odata.context" not in rows[0]


def test_p1_is_debit_minus_credit() -> None:
    balanced = [
        {"debitAmount": "10.00", "creditAmount": "0.00"},
        {"debitAmount": "0.00", "creditAmount": "10.00"},
    ]
    assert gl_p1(balanced) == Decimal("0.00")
    assert gl_p1([{"debitAmount": "5.00", "creditAmount": "0.00"}]) == Decimal("5.00")


def test_population_gap_is_income_plus_balance_minus_v2() -> None:
    assert population_gap(1022, 3362, 4384) == 0
    assert population_gap(1, 1, 3) == -1


def test_month_movement_matches_change_in_ending_balance() -> None:
    rows = [
        _trial("1000", "Posting", "0", "0", "10", "0", date(2026, 8, 31)),
        _trial("1000", "Posting", "5", "0", "15", "0", date(2026, 9, 30)),
        _trial("2000", "Posting", "3", "0", "4", "0", date(2026, 9, 30)),
        _trial("9000", "Total", "100", "0", "0", "0", date(2026, 9, 30)),
    ]
    diffs = movement_diffs(rows)
    assert len(diffs) == 1
    assert diffs[0].account == "2000"
    assert diffs[0].period_end == date(2026, 9, 30)
    assert diffs[0].difference == Decimal("3") - Decimal("4")


def test_ending_balance_ignores_entries_after_the_cutoff() -> None:
    gl = [
        _gl("1000", "2026-09-15", "10.00", "0.00"),
        _gl("1000", "2026-10-01", "99.00", "0.00"),
        _gl("3000", "2026-09-01", "2.00", "0.00"),
    ]
    trial = [
        _trial("1000", "Posting", "10", "0", "10", "0", date(2026, 9, 30)),
        _trial("2000", "Posting", "0", "0", "5", "0", date(2026, 9, 30)),
        _trial("3000", "Heading", "0", "0", "0", "0", date(2026, 9, 30)),
    ]
    diffs = balance_diffs(trial, gl, date(2026, 9, 30))
    assert [item.account for item in diffs] == ["2000", "3000"]
    assert diffs[0].ending == Decimal("5")
    assert diffs[0].cumulative == Decimal("0")
    assert diffs[1].cumulative == Decimal("2.00")


def test_side_gaps_ignore_total_accounts() -> None:
    rows = [
        _trial("1000", "Posting", "8", "3", "8", "3", date(2026, 9, 30)),
        _trial("9000", "Total", "100", "0", "100", "0", date(2026, 9, 30)),
    ]
    gaps = trial_side_gaps(rows)
    assert len(gaps) == 1
    assert gaps[0].movement_gap == Decimal("5.00")
    assert gaps[0].balance_gap == Decimal("5.00")


def _trial(
    account: str,
    account_type: str,
    debit: str,
    credit: str,
    balance_debit: str,
    balance_credit: str,
    end: date,
) -> dict[str, str]:
    return {
        "number": account,
        "accountType": account_type,
        "display": account,
        "totalDebit": debit,
        "totalCredit": credit,
        "balanceAtDateDebit": balance_debit,
        "balanceAtDateCredit": balance_credit,
        "periodStart": end.replace(day=1).isoformat(),
        "periodEnd": end.isoformat(),
    }


def _gl(account: str, posted: str, debit: str, credit: str) -> dict[str, str]:
    return {
        "accountNumber": account,
        "postingDate": posted,
        "debitAmount": debit,
        "creditAmount": credit,
    }
