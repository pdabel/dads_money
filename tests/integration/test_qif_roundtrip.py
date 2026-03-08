"""Integration tests for QIF import/export round-trip."""

from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from dads_money.io_qif import QIFParser, QIFWriter
from dads_money.models import Transaction, TransactionStatus


class TestQIFRoundTrip:
    """Test QIF format round-trip (parse → export → re-parse)."""

    def test_qif_parser_import(self) -> None:
        """Test that QIF module can be imported."""
        assert QIFParser is not None
        assert QIFWriter is not None

    def test_qif_write_and_parse(self) -> None:
        """Test writing QIF and re-parsing it."""
        # Create transactions
        transactions = [
            Transaction(
                account_id="test_account",
                payee="Coffee Shop",
                amount=Decimal("-4.50"),
                check_number="",
                memo="Morning coffee",
            ),
            Transaction(
                account_id="test_account",
                payee="Salary Deposit",
                amount=Decimal("2000.00"),
                check_number="",
                memo="Monthly salary",
            ),
        ]

        # Write to temporary file
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            temp_file = Path(f.name)

        try:
            QIFWriter.write_file(temp_file, transactions)

            # Re-parse the file
            parsed = QIFParser.parse_file(str(temp_file))

            # Verify basic properties
            assert len(parsed) >= len(transactions)
            assert any(t.payee == "Coffee Shop" for t in parsed)
            assert any(t.payee == "Salary Deposit" for t in parsed)

            # Verify amounts (may be string in some implementations)
            amounts = [float(t.amount) for t in parsed]
            assert -4.50 in amounts or Decimal("-4.50") in [t.amount for t in parsed]
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_parser_basic_functionality(self) -> None:
        """Test basic QIF parsing functionality."""
        # Create a simple QIF content
        qif_content = """!Type:Bank
D3/15/2024
T-50.00
PGrocery Store
MWeekly shopping
^
D3/16/2024
T150.00
PBonus
MQuarterly bonus
^
"""
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            assert len(transactions) > 0
            # Verify at least one transaction was parsed
            assert any(t.payee == "Grocery Store" for t in transactions)
        finally:
            temp_file.unlink(missing_ok=True)
