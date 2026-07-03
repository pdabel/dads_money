"""Integration tests for the UK tax report CSV export workflow.

Exercises the full pipeline: create accounts and transactions through
MoneyService → generate a UKTaxReport → export to CSV → re-read the
file and verify the figures.
"""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Generator

import pytest

from dads_money.io_csv import UKTaxReportCSVWriter
from dads_money.models import AccountType
from dads_money.services import MoneyService


@pytest.fixture
def service(tmp_path: Path) -> Generator[MoneyService, None, None]:
    """MoneyService backed by a temporary database."""
    svc = MoneyService(db_path=tmp_path / "test.db")
    yield svc
    svc.close()


class TestTaxReportCSVWorkflow:
    """End-to-end: transactions → tax report → CSV → re-parse."""

    def test_full_workflow(self, service: MoneyService, tmp_path: Path) -> None:
        """Interest and other income figures survive the trip to CSV."""
        savings = service.create_account("Saver", AccountType.SAVINGS, opening_balance=1000.0)
        current = service.create_account("Current", AccountType.CHECKING, opening_balance=0.0)
        interest_cat = service.create_category("Bank Interest", is_income=True)
        salary_cat = service.create_category("Salary", is_income=True)

        # Tax year 2025/26 runs 6 Apr 2025 – 5 Apr 2026
        service.create_transaction(
            savings.id,
            date(2025, 6, 30),
            42.50,
            payee="Big Bank",
            category_id=interest_cat.id,
        )
        service.create_transaction(
            current.id,
            date(2025, 7, 25),
            2500.0,
            payee="Employer",
            category_id=salary_cat.id,
        )
        # Outside the tax year — must be excluded
        service.create_transaction(
            current.id,
            date(2025, 4, 1),
            999.0,
            payee="Employer",
            category_id=salary_cat.id,
        )

        report = service.generate_uk_tax_report(2025, [savings.id, current.id])

        out = tmp_path / "tax.csv"
        UKTaxReportCSVWriter.write_file(str(out), report)

        with open(out, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))

        assert ["Tax Year", "2025/26"] in rows
        assert ["2025-06-30", "Saver", "Big Bank", "42.50", "100", ""] in rows
        assert ["2025-07-25", "Current", "Employer", "Salary", "2500.00", "100"] in rows
        assert ["Total Interest (excl. ISA)", "42.50"] in rows
        assert ["Total Other Income", "2500.00"] in rows
        # The out-of-year transaction must not appear
        assert not any("999" in cell for row in rows for cell in row)
        # No currency symbols anywhere
        assert "£" not in out.read_text(encoding="utf-8-sig")

    def test_joint_account_share_in_csv(self, service: MoneyService, tmp_path: Path) -> None:
        """Joint accounts export halved amounts with a 50 share percentage."""
        joint = service.create_account(
            "Joint Saver", AccountType.SAVINGS, opening_balance=0.0, owner="Joint"
        )
        interest_cat = service.create_category("Interest", is_income=True)
        service.create_transaction(
            joint.id,
            date(2025, 9, 1),
            100.0,
            payee="Big Bank Interest",
            category_id=interest_cat.id,
        )

        report = service.generate_uk_tax_report(2025, [joint.id], joint_account_ids=[joint.id])

        out = tmp_path / "tax.csv"
        UKTaxReportCSVWriter.write_file(str(out), report)

        with open(out, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))

        interest_row = next(r for r in rows if r and r[0] == "2025-09-01")
        assert Decimal(interest_row[3]) == Decimal("50.00")
        assert interest_row[4] == "50"
        assert ["Total Interest (excl. ISA)", "50.00"] in rows
