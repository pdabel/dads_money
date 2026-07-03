"""Unit tests for UKTaxReportCSVWriter (Excel-friendly tax report export)."""

import csv
from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest

from dads_money.io_csv import UKTaxReportCSVWriter
from dads_money.models import (
    CapitalGainEvent,
    InvestmentIncomeItem,
    OtherIncomeItem,
    SavingsInterestItem,
    UKTaxReport,
)


def _sample_report() -> UKTaxReport:
    """Build a report exercising every section, including ISA and joint rows."""
    return UKTaxReport(
        tax_year_start=2024,
        capital_gains=[
            CapitalGainEvent(
                date=date(2024, 6, 1),
                account_name="Broker",
                security_name="Acme PLC",
                quantity=Decimal("100"),
                proceeds=Decimal("1500.00"),
                cost=Decimal("1000.00"),
                gain=Decimal("500.00"),
            ),
            CapitalGainEvent(
                date=date(2024, 9, 15),
                account_name="Shares ISA",
                security_name="Widget Fund",
                quantity=Decimal("50.5"),
                proceeds=Decimal("600.00"),
                cost=Decimal("700.00"),
                gain=Decimal("-100.00"),
                is_isa=True,
            ),
        ],
        investment_income=[
            InvestmentIncomeItem(
                date=date(2024, 7, 1),
                account_name="Broker",
                security_name="Acme PLC",
                income_type="Dividend",
                amount=Decimal("80.00"),
            ),
            InvestmentIncomeItem(
                date=date(2024, 8, 1),
                account_name="Broker",
                security_name="",
                income_type="Interest Income",
                amount=Decimal("12.34"),
            ),
        ],
        savings_interest=[
            SavingsInterestItem(
                date=date(2024, 10, 1),
                account_name="Joint Saver",
                payee="Big Bank",
                amount=Decimal("25.00"),
                share_pct=50,
            ),
        ],
        other_income=[
            OtherIncomeItem(
                date=date(2024, 11, 5),
                account_name="Current",
                payee="Employer",
                category_name="Salary",
                amount=Decimal("2000.00"),
            ),
        ],
    )


def _rows(report: UKTaxReport) -> list:
    """Write a report to a string buffer and return the parsed CSV rows."""
    buf = StringIO()
    UKTaxReportCSVWriter.write(buf, report)
    buf.seek(0)
    return list(csv.reader(buf))


class TestUKTaxReportCSVWriter:
    """Tests for the UK tax report CSV export."""

    def test_title_and_tax_year(self) -> None:
        """Report header names the tax year."""
        rows = _rows(_sample_report())
        assert ["UK Tax Report"] in rows
        assert ["Tax Year", "2024/25"] in rows

    def test_summary_section(self) -> None:
        """Summary totals are plain numbers excluding ISA amounts."""
        rows = _rows(_sample_report())
        assert ["Summary"] in rows
        assert ["Net Capital Gain / (Loss)", "500.00"] in rows
        assert ["Total Dividends (excl. ISA)", "80.00"] in rows
        assert ["Total Interest (excl. ISA)", "37.34"] in rows
        assert ["Total Other Income", "2000.00"] in rows

    def test_capital_gains_section(self) -> None:
        """Capital gains rows carry ISO dates, plain numbers and ISA flag."""
        rows = _rows(_sample_report())
        assert [
            "Date",
            "Account",
            "Security",
            "Quantity",
            "Proceeds",
            "Cost",
            "Gain/(Loss)",
            "Share %",
            "ISA Exempt",
        ] in rows
        assert [
            "2024-06-01",
            "Broker",
            "Acme PLC",
            "100",
            "1500.00",
            "1000.00",
            "500.00",
            "100",
            "",
        ] in rows
        assert [
            "2024-09-15",
            "Shares ISA",
            "Widget Fund",
            "50.5",
            "600.00",
            "700.00",
            "-100.00",
            "100",
            "Yes",
        ] in rows
        assert ["Total Gains (excl. ISA)", "500.00"] in rows
        assert ["Total Losses (excl. ISA)", "0.00"] in rows

    def test_dividends_section(self) -> None:
        """Dividend rows appear with totals."""
        rows = _rows(_sample_report())
        assert ["Dividends"] in rows
        assert ["2024-07-01", "Broker", "Acme PLC", "Dividend", "80.00", "100", ""] in rows
        assert ["Total Dividends (excl. ISA)", "80.00"] in rows

    def test_interest_section_merges_investment_and_savings(self) -> None:
        """Interest section includes both investment and savings interest rows."""
        rows = _rows(_sample_report())
        assert ["Interest"] in rows
        assert ["2024-08-01", "Broker", "Interest Income", "12.34", "100", ""] in rows
        assert ["2024-10-01", "Joint Saver", "Big Bank", "25.00", "50", ""] in rows
        assert ["Total Interest (excl. ISA)", "37.34"] in rows

    def test_other_income_section(self) -> None:
        """Other income rows carry payee, category and share percentage."""
        rows = _rows(_sample_report())
        assert ["Other Income"] in rows
        assert ["2024-11-05", "Current", "Employer", "Salary", "2000.00", "100"] in rows
        assert ["Total Other Income", "2000.00"] in rows

    def test_no_currency_symbols(self) -> None:
        """The export contains no pound signs."""
        buf = StringIO()
        UKTaxReportCSVWriter.write(buf, _sample_report())
        assert "£" not in buf.getvalue()

    def test_empty_report_sections(self) -> None:
        """An empty report still writes section headers with (none) markers."""
        rows = _rows(UKTaxReport(tax_year_start=2023))
        assert ["Tax Year", "2023/24"] in rows
        assert ["Capital Gains"] in rows
        assert rows.count(["(none)"]) == 4  # one per detail section

    def test_write_file_uses_utf8_sig(self, tmp_path: Path) -> None:
        """write_file produces a UTF-8 BOM so Excel decodes it correctly."""
        out = tmp_path / "tax.csv"
        UKTaxReportCSVWriter.write_file(str(out), _sample_report())
        assert out.read_bytes().startswith(b"\xef\xbb\xbf")

    def test_write_file_round_trips(self, tmp_path: Path) -> None:
        """A file written to disk can be re-read with the csv module."""
        out = tmp_path / "tax.csv"
        UKTaxReportCSVWriter.write_file(str(out), _sample_report())
        with open(out, "r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        gain_row = next(r for r in rows if r and r[0] == "2024-06-01")
        assert Decimal(gain_row[6]) == Decimal("500.00")
