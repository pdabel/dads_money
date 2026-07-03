"""Unit tests for AccountSummaryCSVWriter (Excel-friendly report export)."""

import csv
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest

from dads_money.io_csv import AccountSummaryCSVWriter
from dads_money.models import (
    AccountSummaryEntry,
    AccountSummaryReport,
    CategorySummaryRow,
)


def _sample_report() -> AccountSummaryReport:
    """Build a two-account report with income and expense categories."""
    return AccountSummaryReport(
        start_date=date(2025, 4, 6),
        end_date=date(2026, 4, 5),
        entries=[
            AccountSummaryEntry(
                account_name="Current",
                account_type="Current Account",
                opening_balance=Decimal("1000.00"),
                closing_balance=Decimal("1300.00"),
                total_credits=Decimal("2500.00"),
                total_debits=Decimal("2200.00"),
                category_breakdown=[
                    CategorySummaryRow(category_name="Salary", amount=Decimal("2500.00")),
                    CategorySummaryRow(category_name="Groceries", amount=Decimal("-2200.00")),
                ],
                transaction_count=14,
            ),
            AccountSummaryEntry(
                account_name="Savings",
                account_type="Savings",
                opening_balance=Decimal("5000.00"),
                closing_balance=Decimal("5050.00"),
                total_credits=Decimal("50.00"),
                total_debits=Decimal("0.00"),
                category_breakdown=[
                    CategorySummaryRow(category_name="Interest", amount=Decimal("50.00")),
                ],
                transaction_count=1,
            ),
        ],
    )


def _rows(report: AccountSummaryReport) -> list:
    """Write a report to a string buffer and return the parsed CSV rows."""
    buf = StringIO()
    AccountSummaryCSVWriter.write(buf, report)
    buf.seek(0)
    return list(csv.reader(buf))


class TestAccountSummaryCSVWriter:
    """Tests for the account summary CSV export."""

    def test_overview_header_row(self) -> None:
        """Overview section has the expected column headers."""
        rows = _rows(_sample_report())
        assert [
            "Account",
            "Type",
            "Opening Balance",
            "Credits",
            "Debits",
            "Net Change",
            "Closing Balance",
            "Transactions",
        ] in rows

    def test_amounts_are_plain_numbers(self) -> None:
        """Amounts contain no currency symbols or thousands separators."""
        rows = _rows(_sample_report())
        account_row = next(r for r in rows if r and r[0] == "Current")
        assert account_row[2] == "1000.00"
        assert account_row[3] == "2500.00"
        assert account_row[4] == "2200.00"
        assert account_row[5] == "300.00"
        assert account_row[6] == "1300.00"
        assert account_row[7] == "14"

    def test_negative_net_change_is_signed_number(self) -> None:
        """A net loss is written as a plain negative number."""
        report = AccountSummaryReport(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            entries=[
                AccountSummaryEntry(
                    account_name="Cash",
                    account_type="Cash",
                    opening_balance=Decimal("100.00"),
                    closing_balance=Decimal("40.00"),
                    total_credits=Decimal("0.00"),
                    total_debits=Decimal("60.00"),
                    category_breakdown=[],
                    transaction_count=3,
                )
            ],
        )
        rows = _rows(report)
        account_row = next(r for r in rows if r and r[0] == "Cash")
        assert account_row[5] == "-60.00"

    def test_period_dates_are_iso(self) -> None:
        """Period start/end use ISO YYYY-MM-DD format."""
        rows = _rows(_sample_report())
        assert ["Period Start", "2025-04-06"] in rows
        assert ["Period End", "2026-04-05"] in rows

    def test_totals_row(self) -> None:
        """TOTALS row aggregates credits, debits, net change and count."""
        rows = _rows(_sample_report())
        totals_row = next(r for r in rows if r and r[0] == "TOTALS")
        assert totals_row[3] == "2550.00"
        assert totals_row[4] == "2200.00"
        assert totals_row[5] == "350.00"
        assert totals_row[7] == "15"

    def test_income_by_category_section(self) -> None:
        """Income categories are listed with a total."""
        rows = _rows(_sample_report())
        assert ["Income by Category"] in rows
        assert ["Salary", "2500.00"] in rows
        assert ["Interest", "50.00"] in rows
        assert ["Total Income", "2550.00"] in rows

    def test_expenses_by_category_section(self) -> None:
        """Expense categories are listed as absolute values with a total."""
        rows = _rows(_sample_report())
        assert ["Expenses by Category"] in rows
        assert ["Groceries", "2200.00"] in rows
        assert ["Total Expenses", "2200.00"] in rows

    def test_empty_report(self) -> None:
        """A report with no entries still writes headers and empty sections."""
        report = AccountSummaryReport(start_date=date(2025, 1, 1), end_date=date(2025, 12, 31))
        rows = _rows(report)
        assert ["Account Summary Report"] in rows
        assert ["(none)"] in rows

    def test_unicode_names_preserved(self) -> None:
        """Accented account and category names survive the export."""
        report = AccountSummaryReport(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            entries=[
                AccountSummaryEntry(
                    account_name="Café Fund",
                    account_type="Savings",
                    opening_balance=Decimal("0.00"),
                    closing_balance=Decimal("10.00"),
                    total_credits=Decimal("10.00"),
                    total_debits=Decimal("0.00"),
                    category_breakdown=[
                        CategorySummaryRow(category_name="Curaçao Trip", amount=Decimal("10.00")),
                    ],
                    transaction_count=1,
                )
            ],
        )
        rows = _rows(report)
        assert any(r and r[0] == "Café Fund" for r in rows)
        assert ["Curaçao Trip", "10.00"] in rows

    def test_write_file_uses_utf8_sig(self, tmp_path: Path) -> None:
        """write_file produces a UTF-8 BOM so Excel decodes it correctly."""
        out = tmp_path / "summary.csv"
        AccountSummaryCSVWriter.write_file(str(out), _sample_report())
        raw = out.read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf")

    def test_write_file_round_trips(self, tmp_path: Path) -> None:
        """A file written to disk can be re-read with the csv module."""
        out = tmp_path / "summary.csv"
        AccountSummaryCSVWriter.write_file(str(out), _sample_report())
        with open(out, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        assert ["Account Summary Report"] in rows
        account_row = next(r for r in rows if r and r[0] == "Current")
        assert Decimal(account_row[3]) == Decimal("2500.00")
