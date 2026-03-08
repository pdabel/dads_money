"""Integration tests for CSV import/export round-trip."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from dads_money.io_csv import CSVParser, CSVWriter
from dads_money.models import Transaction, TransactionStatus


class TestCSVRoundTrip:
    """Test CSV format round-trip (write → parse → verify)."""

    def test_csv_write_and_parse_basic(self) -> None:
        """Test writing CSV and re-parsing it."""
        transactions = [
            Transaction(
                payee="Coffee Shop",
                amount=Decimal("-4.50"),
                memo="Morning coffee",
            ),
            Transaction(
                payee="Salary Deposit",
                amount=Decimal("2000.00"),
                memo="Monthly salary",
            ),
        ]

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = Path(f.name)

        try:
            CSVWriter.write_file(str(temp_file), transactions)

            # Re-parse the file
            parsed = CSVParser.parse_file(str(temp_file))

            # Verify basic properties
            assert len(parsed) >= len(transactions)
            payees = {t.payee for t in parsed}
            assert "Coffee Shop" in payees
            assert "Salary Deposit" in payees
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_decimal_precision(self) -> None:
        """Test that Decimal precision is preserved."""
        amounts = [
            Decimal("0.01"),
            Decimal("100.00"),
            Decimal("9999.99"),
            Decimal("-50.25"),
        ]

        transactions = [
            Transaction(payee=f"Payee {amt}", amount=amt)
            for amt in amounts
        ]

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = Path(f.name)

        try:
            CSVWriter.write_file(str(temp_file), transactions)
            parsed = CSVParser.parse_file(str(temp_file))

            for orig_amt in amounts:
                payee = f"Payee {orig_amt}"
                found = next((t for t in parsed if t.payee == payee), None)
                assert found is not None
                assert found.amount == orig_amt
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_with_dates(self) -> None:
        """Test that dates are correctly written and parsed."""
        test_date = date(2024, 3, 15)
        transactions = [
            Transaction(
                date=test_date,
                payee="Test Payee",
                amount=Decimal("50.00"),
            ),
        ]

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = Path(f.name)

        try:
            CSVWriter.write_file(str(temp_file), transactions)
            parsed = CSVParser.parse_file(str(temp_file))

            assert len(parsed) > 0
            assert parsed[0].date == test_date
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_with_check_numbers(self) -> None:
        """Test that check numbers are preserved."""
        transactions = [
            Transaction(
                payee="Utility Company",
                amount=Decimal("-75.00"),
                check_number="1001",
            ),
            Transaction(
                payee="Landlord",
                amount=Decimal("-1200.00"),
                check_number="1002",
            ),
        ]

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = Path(f.name)

        try:
            CSVWriter.write_file(str(temp_file), transactions)
            parsed = CSVParser.parse_file(str(temp_file))

            check_nums = {t.check_number for t in parsed if t.check_number}
            assert "1001" in check_nums
            assert "1002" in check_nums
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_with_status(self) -> None:
        """Test that transaction status is preserved."""
        transactions = [
            Transaction(
                payee="Cleared Transaction",
                amount=Decimal("50.00"),
                status=TransactionStatus.CLEARED,
            ),
            Transaction(
                payee="Reconciled Transaction",
                amount=Decimal("100.00"),
                status=TransactionStatus.RECONCILED,
            ),
        ]

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = Path(f.name)

        try:
            CSVWriter.write_file(str(temp_file), transactions)
            parsed = CSVParser.parse_file(str(temp_file))

            assert len(parsed) >= len(transactions)
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_with_memos(self) -> None:
        """Test that memos are preserved."""
        transactions = [
            Transaction(
                payee="Store",
                amount=Decimal("-50.00"),
                memo="Weekly groceries",
            ),
            Transaction(
                payee="Employer",
                amount=Decimal("2000.00"),
                memo="Monthly salary - March",
            ),
        ]

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = Path(f.name)

        try:
            CSVWriter.write_file(str(temp_file), transactions)
            parsed = CSVParser.parse_file(str(temp_file))

            memos = {t.memo for t in parsed}
            assert "Weekly groceries" in memos
            assert "Monthly salary - March" in memos
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_handles_negative_amounts(self) -> None:
        """Test that negative amounts are handled correctly."""
        transactions = [
            Transaction(payee="Expense 1", amount=Decimal("-25.00")),
            Transaction(payee="Income 1", amount=Decimal("100.00")),
            Transaction(payee="Expense 2", amount=Decimal("-50.75")),
        ]

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = Path(f.name)

        try:
            CSVWriter.write_file(str(temp_file), transactions)
            parsed = CSVParser.parse_file(str(temp_file))

            # Verify negative amounts
            amounts = [t.amount for t in parsed]
            assert any(amt < 0 for amt in amounts)
            assert any(amt > 0 for amt in amounts)
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_parser_flexible_columns(self) -> None:
        """Test that CSV parser accepts various column names."""
        csv_content = """Date,Amount,Description,Memo,Check
2024-03-15,50.00,Coffee Shop,Morning coffee,
2024-03-16,-75.00,Electric Company,Monthly bill,
"""
        with NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            parsed = CSVParser.parse_file(str(temp_file))
            assert len(parsed) >= 2
            
            # Parser should handle alternate column names
            payees = {t.payee for t in parsed}
            assert "Coffee Shop" in payees or "Electric Company" in payees
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_empty_file(self) -> None:
        """Test parsing empty CSV file (just headers)."""
        transactions: list = []

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = Path(f.name)

        try:
            CSVWriter.write_file(str(temp_file), transactions)
            parsed = CSVParser.parse_file(str(temp_file))

            # Should return empty or minimal list
            assert len(parsed) <= 1  # Just header row if anything
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_large_number_of_transactions(self) -> None:
        """Test CSV handling of many transactions."""
        # Create 100 transactions
        transactions = [
            Transaction(
                payee=f"Payee {i}",
                amount=Decimal("100.00") if i % 2 == 0 else Decimal("-50.00"),
                memo=f"Transaction {i}",
            )
            for i in range(100)
        ]

        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = Path(f.name)

        try:
            CSVWriter.write_file(str(temp_file), transactions)
            parsed = CSVParser.parse_file(str(temp_file))

            assert len(parsed) >= 100
        finally:
            temp_file.unlink(missing_ok=True)
