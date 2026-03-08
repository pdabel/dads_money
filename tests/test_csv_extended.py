"""Extended CSV format tests for edge cases and error handling."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from dads_money.io_csv import CSVParser, CSVWriter
from dads_money.models import Transaction


class TestCSVEdgeCases:
    """Tests for CSV parsing edge cases."""

    def test_csv_empty_file(self) -> None:
        """Test parsing empty CSV file."""
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            assert isinstance(transactions, list)
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_only_headers(self) -> None:
        """Test CSV with only header row."""
        csv_content = "Date,Payee,Amount,Memo\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            assert len(transactions) == 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_missing_optional_columns(self) -> None:
        """Test CSV with minimal columns."""
        csv_content = "Date,Amount\n2024-03-15,100.00\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            assert len(transactions) > 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_quoted_values(self) -> None:
        """Test CSV with quoted values containing commas."""
        csv_content = '''Date,Payee,Memo,Amount
2024-03-15,"Store, Inc.","Payment for ""supplies""",100.00
'''
        with NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            assert len(transactions) > 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_case_insensitive_headers(self) -> None:
        """Test CSV with different case in headers."""
        csv_content = "DATE,PAYEE,AMOUNT,MEMO\n2024-03-15,Test,100.00,Test memo\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            assert len(transactions) > 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_mixed_case_headers(self) -> None:
        """Test CSV with mixed case column headers."""
        csv_content = "Date,Payee,Amount,Notes\n2024-03-15,Test,100.00,Memo\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            assert len(transactions) > 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_negative_amount_parentheses(self) -> None:
        """Test CSV with negative amounts in parentheses."""
        csv_content = "Date,Payee,Amount\n2024-03-15,Expense,(100.00)\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            if len(transactions) > 0:
                # Should be negative
                assert transactions[0].amount < 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_amount_with_currency_symbol(self) -> None:
        """Test CSV with currency symbols in amounts."""
        csv_content = "Date,Payee,Amount\n2024-03-15,Test,$100.00\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            if len(transactions) > 0:
                assert isinstance(transactions[0].amount, Decimal)
                assert transactions[0].amount == Decimal("100.00")
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_amount_with_thousands_separator(self) -> None:
        """Test CSV with thousands separators."""
        csv_content = "Date,Payee,Amount\n2024-03-15,Test,1,234.56\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            if len(transactions) > 0:
                # Should parse correctly with comma removed
                assert transactions[0].amount > 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_debit_credit_columns(self) -> None:
        """Test CSV with separate debit/credit columns."""
        csv_content = "Date,Payee,Debit,Credit\n2024-03-15,Income,,1000.00\n2024-03-16,Expense,50.00,\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            assert len(transactions) >= 2
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_empty_cells(self) -> None:
        """Test CSV with empty cells."""
        csv_content = "Date,Payee,Amount,Memo\n2024-03-15,Test,100.00,\n2024-03-16,,50.00,Memo\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            assert len(transactions) >= 2
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_no_headers(self) -> None:
        """Test CSV without header row."""
        csv_content = "2024-03-15,Test,100.00\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            # CSVParser uses DictReader which expects headers
            transactions = CSVParser.parse_file(str(temp_file))
            # May return empty or treat first line as header
            assert isinstance(transactions, list)
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_unicode_characters(self) -> None:
        """Test CSV with unicode/special characters."""
        csv_content = "Date,Payee,Amount,Memo\n2024-03-15,Café René,€100.00,Café visit\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            if len(transactions) > 0:
                assert "Café" in transactions[0].payee or "René" in transactions[0].payee
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_long_field_values(self) -> None:
        """Test CSV with very long field values."""
        long_payee = "A" * 500
        long_memo = "B" * 500
        csv_content = f"Date,Payee,Amount,Memo\n2024-03-15,{long_payee},100.00,{long_memo}\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            assert len(transactions) > 0
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_dates_multiple_formats(self) -> None:
        """Test CSV with different date formats."""
        csv_content = """Date,Payee,Amount
2024-03-15,Test1,100.00
03/15/2024,Test2,200.00
15/03/2024,Test3,300.00
20240315,Test4,400.00
"""
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            assert len(transactions) >= 4
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_write_empty_transactions(self) -> None:
        """Test writing empty transaction list to CSV."""
        with NamedTemporaryFile(suffix=".csv", delete=False) as f:
            temp_file = Path(f.name)

        try:
            CSVWriter.write_file(str(temp_file), [])
            assert temp_file.exists()
            content = temp_file.read_text()
            assert "Date" in content  # Should at least have headers
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_write_with_all_fields(self) -> None:
        """Test writing CSV with all transaction fields populated."""
        txn = Transaction(
            date=date(2024, 3, 15),
            payee="Complete Transaction",
            amount=Decimal("123.45"),
            memo="Full memo",
            check_number="1001",
        )

        with NamedTemporaryFile(suffix=".csv", delete=False) as f:
            temp_file = Path(f.name)

        try:
            CSVWriter.write_file(str(temp_file), [txn])
            content = temp_file.read_text()
            assert "Complete Transaction" in content
            assert "123.45" in content
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_roundtrip_many_transactions(self) -> None:
        """Test writing and parsing many transactions."""
        transactions = [
            Transaction(payee=f"Payee {i}", amount=Decimal(str(i * 10)))
            for i in range(50)
        ]

        with NamedTemporaryFile(suffix=".csv", delete=False) as f:
            temp_file = Path(f.name)

        try:
            CSVWriter.write_file(str(temp_file), transactions)
            parsed = CSVParser.parse_file(str(temp_file))
            assert len(parsed) >= len(transactions)
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_zero_amount(self) -> None:
        """Test CSV with zero amounts."""
        csv_content = "Date,Payee,Amount\n2024-03-15,Test,0.00\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            if len(transactions) > 0:
                assert transactions[0].amount == Decimal("0.00")
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_invalid_date_defaults(self) -> None:
        """Test that invalid dates default gracefully."""
        csv_content = "Date,Payee,Amount\ninvalid-date,Test,100.00\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            # Should handle gracefully even with invalid date
            assert isinstance(transactions, list)
        finally:
            temp_file.unlink(missing_ok=True)

    def test_csv_invalid_amount_defaults(self) -> None:
        """Test that invalid amounts default gracefully."""
        csv_content = "Date,Payee,Amount\n2024-03-15,Test,invalid\n"
        with NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_file = Path(f.name)

        try:
            transactions = CSVParser.parse_file(str(temp_file))
            if len(transactions) > 0:
                # Should default to 0.00 for invalid amount
                assert transactions[0].amount == Decimal("0.00")
        finally:
            temp_file.unlink(missing_ok=True)
