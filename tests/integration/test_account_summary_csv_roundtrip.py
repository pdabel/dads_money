"""Integration tests for the account summary report CSV export workflow.

Exercises the full pipeline: create accounts and transactions through
MoneyService → generate an AccountSummaryReport → export to CSV →
re-read the file and verify the figures.
"""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Generator

import pytest

from dads_money.io_csv import AccountSummaryCSVWriter
from dads_money.models import AccountType
from dads_money.services import MoneyService


@pytest.fixture
def service(tmp_path: Path) -> Generator[MoneyService, None, None]:
    """MoneyService backed by a temporary database."""
    svc = MoneyService(db_path=tmp_path / "test.db")
    yield svc
    svc.close()


class TestAccountSummaryCSVWorkflow:
    """End-to-end: transactions → report → CSV → re-parse."""

    def test_full_workflow(self, service: MoneyService, tmp_path: Path) -> None:
        """Figures survive the trip from database to CSV intact."""
        account = service.create_account(
            "Dad's Current", AccountType.CHECKING, opening_balance=500.0
        )
        salary = service.create_category("Salary", is_income=True)
        groceries = service.create_category("Groceries", is_income=False)

        service.create_transaction(
            account.id,
            date(2025, 5, 1),
            2000.0,
            payee="Employer",
            category_id=salary.id,
        )
        service.create_transaction(
            account.id,
            date(2025, 5, 10),
            -150.25,
            payee="Supermarket",
            category_id=groceries.id,
        )
        # Outside the report period — must be excluded from credits/debits
        service.create_transaction(
            account.id,
            date(2024, 1, 1),
            100.0,
            payee="Old deposit",
            category_id=salary.id,
        )

        report = service.generate_account_summary(date(2025, 4, 6), date(2026, 4, 5), [account.id])

        out = tmp_path / "summary.csv"
        AccountSummaryCSVWriter.write_file(str(out), report)

        with open(out, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))

        account_row = next(r for r in rows if r and r[0] == "Dad's Current")
        # Opening balance includes the pre-period transaction: 500 + 100
        assert Decimal(account_row[2]) == Decimal("600.00")
        assert Decimal(account_row[3]) == Decimal("2000.00")
        assert Decimal(account_row[4]) == Decimal("150.25")
        assert Decimal(account_row[5]) == Decimal("1849.75")
        assert Decimal(account_row[6]) == Decimal("2449.75")
        assert account_row[7] == "2"

        assert ["Salary", "2000.00"] in rows
        assert ["Groceries", "150.25"] in rows
        assert ["Period Start", "2025-04-06"] in rows
        assert ["Period End", "2026-04-05"] in rows

        # No currency symbols anywhere in the file
        text = out.read_text(encoding="utf-8-sig")
        assert "£" not in text and "$" not in text and "€" not in text

    def test_multi_account_totals(self, service: MoneyService, tmp_path: Path) -> None:
        """TOTALS row aggregates across accounts in the exported file."""
        acc1 = service.create_account("Current", AccountType.CHECKING, opening_balance=0.0)
        acc2 = service.create_account("Savings", AccountType.SAVINGS, opening_balance=1000.0)
        interest = service.create_category("Interest", is_income=True)

        service.create_transaction(acc1.id, date(2025, 6, 1), 300.0, payee="Deposit")
        service.create_transaction(
            acc2.id, date(2025, 6, 30), 12.50, payee="Bank", category_id=interest.id
        )

        report = service.generate_account_summary(
            date(2025, 4, 6), date(2026, 4, 5), [acc1.id, acc2.id]
        )
        out = tmp_path / "summary.csv"
        AccountSummaryCSVWriter.write_file(str(out), report)

        with open(out, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))

        totals_row = next(r for r in rows if r and r[0] == "TOTALS")
        assert Decimal(totals_row[3]) == Decimal("312.50")
        assert Decimal(totals_row[4]) == Decimal("0.00")
        assert Decimal(totals_row[5]) == Decimal("312.50")
        assert totals_row[7] == "2"
