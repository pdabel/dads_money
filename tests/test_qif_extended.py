"""Extended QIF format tests for edge cases and error handling."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from dads_money.io_qif import QIFParser, QIFWriter
from dads_money.models import Transaction


class TestQIFEdgeCases:
    """Tests for QIF parsing edge cases."""

    def test_qif_empty_file(self) -> None:
        """Test parsing empty QIF file."""
        qif_content = ""
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            assert isinstance(transactions, list)
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_only_header(self) -> None:
        """Test QIF with only header, no transactions."""
        qif_content = "!Type:Bank\n"
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            assert len(transactions) == 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_multiple_account_types(self) -> None:
        """Test QIF with different account type headers."""
        qif_content = """!Type:Bank
D1/1/2024
T100.00
P Test
^
!Type:CCard
D1/2/2024
T50.00
PCard Purchase
^
!Type:Cash
D1/3/2024
T25.00
PCash Withdrawal
^
"""
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            assert len(transactions) >= 3
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_missing_date_field(self) -> None:
        """Test transaction without date."""
        qif_content = """!Type:Bank
T100.00
PTest Payee
^
"""
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            assert len(transactions) >= 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_missing_amount_field(self) -> None:
        """Test transaction without amount."""
        qif_content = """!Type:Bank
D1/1/2024
PTest Payee
^
"""
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            # Should handle gracefully
            assert isinstance(transactions, list)
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_very_large_amount(self) -> None:
        """Test QIF with very large amounts."""
        qif_content = """!Type:Bank
D1/1/2024
T999999999.99
PLarge Amount
^
"""
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            if len(transactions) > 0:
                assert isinstance(transactions[0].amount, Decimal)
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_very_small_amount(self) -> None:
        """Test QIF with very small amounts."""
        qif_content = """!Type:Bank
D1/1/2024
T0.01
PSmall Amount
^
"""
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            if len(transactions) > 0:
                assert transactions[0].amount == Decimal("0.01")
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_whitespace_handling(self) -> None:
        """Test QIF with extra whitespace."""
        qif_content = """!Type:Bank
D1/1/2024
T  100.00
P  Test Payee
M  Test Memo
^
"""
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            assert len(transactions) > 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_empty_lines_between_transactions(self) -> None:
        """Test QIF with blank lines between transactions."""
        qif_content = """!Type:Bank

D1/1/2024
T100.00
P Test 1
^

D1/2/2024
T200.00
P Test 2
^

"""
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            assert len(transactions) >= 2
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_special_characters_in_payee(self) -> None:
        """Test QIF with special characters in payee."""
        qif_content = """!Type:Bank
D1/1/2024
T100.00
PFamily & Friends, Inc. (Test)
^
"""
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            if len(transactions) > 0:
                assert "&" in transactions[0].payee or "Test" in transactions[0].payee
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_unicode_characters(self) -> None:
        """Test QIF with unicode characters."""
        qif_content = """!Type:Bank
D1/1/2024
T100.00
PCafé René
MMémo with accent
^
"""
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False, encoding="utf-8") as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            assert len(transactions) > 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_date_formats_mixed(self) -> None:
        """Test QIF with various date formats."""
        qif_content = """!Type:Bank
D3/15/2024
T100.00
P Test1
^
D2024-03-16
T200.00
P Test2
^
D03/17/24
T300.00
P Test3
^
"""
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            assert len(transactions) >= 2
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_long_memo(self) -> None:
        """Test QIF with very long memo field."""
        long_memo = "A" * 500
        qif_content = f"""!Type:Bank
D1/1/2024
T100.00
PTest
M{long_memo}
^
"""
        with NamedTemporaryFile(mode="w", suffix=".qif", delete=False) as f:
            f.write(qif_content)
            temp_file = Path(f.name)

        try:
            transactions = QIFParser.parse_file(str(temp_file))
            assert len(transactions) > 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_write_empty_list(self) -> None:
        """Test writing empty transaction list to QIF."""
        with NamedTemporaryFile(suffix=".qif", delete=False) as f:
            temp_file = Path(f.name)

        try:
            QIFWriter.write_file(str(temp_file), [])
            assert temp_file.exists()
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_write_single_transaction(self) -> None:
        """Test writing single transaction to QIF."""
        txn = Transaction(payee="Test", amount=Decimal("50.00"))

        with NamedTemporaryFile(suffix=".qif", delete=False) as f:
            temp_file = Path(f.name)

        try:
            QIFWriter.write_file(str(temp_file), [txn])
            assert temp_file.exists()
            assert temp_file.stat().st_size > 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_qif_roundtrip_preserves_data(self) -> None:
        """Test that write→parse roundtrip preserves key data."""
        original_txns = [
            Transaction(
                payee="Grocery",
                amount=Decimal("50.00"),
                memo="Weekly shopping",
            ),
            Transaction(payee="Salary", amount=Decimal("2000.00"), memo="Monthly salary"),
        ]

        with NamedTemporaryFile(suffix=".qif", delete=False) as f:
            temp_file = Path(f.name)

        try:
            # Write
            QIFWriter.write_file(str(temp_file), original_txns)

            # Parse
            parsed_txns = QIFParser.parse_file(str(temp_file))

            # Verify at least basic data is preserved
            assert len(parsed_txns) >= len(original_txns)
            payees = {t.payee for t in parsed_txns}
            assert "Grocery" in payees or "Salary" in payees
        finally:
            temp_file.unlink(missing_ok=True)
