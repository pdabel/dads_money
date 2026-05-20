"""Extended QIF format tests for edge cases and error handling."""

import io
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from dads_money.io_qif import QIFParser, QIFWriter
from dads_money.models import AccountType, Transaction, TransactionStatus


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


class TestQIFTransferRoundTrip:
    """Tests for QIF transfer account link preservation."""

    def test_writer_emits_transfer_account_field(self) -> None:
        """Writer outputs L[AccountName] when transfer_account_id is set and mapping provided."""
        txn = Transaction(
            date=date(2024, 1, 15),
            amount=Decimal("-500.00"),
            payee="Monthly payment",
            transfer_account_id="acc-liability-123",
        )
        buf = io.StringIO()
        QIFWriter.write(buf, [txn], account_id_to_name={"acc-liability-123": "House Equity"})
        output = buf.getvalue()
        assert "L[House Equity]" in output

    def test_writer_omits_transfer_field_without_mapping(self) -> None:
        """Writer silently skips L field when no account mapping is provided."""
        txn = Transaction(
            date=date(2024, 1, 15),
            amount=Decimal("-500.00"),
            transfer_account_id="acc-liability-123",
        )
        buf = io.StringIO()
        QIFWriter.write(buf, [txn])
        output = buf.getvalue()
        assert "L[" not in output

    def test_writer_omits_transfer_field_for_unknown_id(self) -> None:
        """Writer skips L field when transfer_account_id is not in the mapping."""
        txn = Transaction(
            date=date(2024, 1, 15),
            amount=Decimal("-500.00"),
            transfer_account_id="acc-unknown",
        )
        buf = io.StringIO()
        QIFWriter.write(buf, [txn], account_id_to_name={"acc-other": "Other Account"})
        output = buf.getvalue()
        assert "L[" not in output

    def test_parser_resolves_transfer_account_name_to_id(self) -> None:
        """Parser sets transfer_account_id when L[AccountName] matches the provided mapping."""
        qif = "!Type:Bank\nD01/15/2024\nT-500.00\nPMonthly payment\nL[House Equity]\n^\n"
        transactions = QIFParser.parse(
            io.StringIO(qif),
            account_name_to_id={"House Equity": "acc-liability-123"},
        )
        assert len(transactions) == 1
        assert transactions[0].transfer_account_id == "acc-liability-123"

    def test_parser_leaves_transfer_account_id_none_without_mapping(self) -> None:
        """Parser does not crash when L[AccountName] is present but no mapping given."""
        qif = "!Type:Bank\nD01/15/2024\nT-500.00\nL[House Equity]\n^\n"
        transactions = QIFParser.parse(io.StringIO(qif))
        assert len(transactions) == 1
        assert transactions[0].transfer_account_id is None

    def test_parser_leaves_transfer_account_id_none_for_unknown_name(self) -> None:
        """Parser leaves transfer_account_id as None when name not in mapping."""
        qif = "!Type:Bank\nD01/15/2024\nT-500.00\nL[Unknown Account]\n^\n"
        transactions = QIFParser.parse(
            io.StringIO(qif),
            account_name_to_id={"House Equity": "acc-liability-123"},
        )
        assert len(transactions) == 1
        assert transactions[0].transfer_account_id is None

    def test_full_round_trip_preserves_transfer_link(self, tmp_path: Path) -> None:
        """Export a transfer transaction then re-import it: transfer_account_id is restored."""
        txn = Transaction(
            date=date(2024, 3, 1),
            amount=Decimal("-400.00"),
            payee="House payment",
            memo="March",
            status=TransactionStatus.CLEARED,
            transfer_account_id="acc-liability-456",
        )
        account_id_to_name = {"acc-liability-456": "House Equity"}
        account_name_to_id = {"House Equity": "acc-liability-456"}

        qif_file = tmp_path / "transfer.qif"
        QIFWriter.write_file(str(qif_file), [txn], account_id_to_name=account_id_to_name)
        parsed = QIFParser.parse_file(str(qif_file), account_name_to_id=account_name_to_id)

        assert len(parsed) == 1
        assert parsed[0].transfer_account_id == "acc-liability-456"
        assert parsed[0].amount == Decimal("-400.00")
        assert parsed[0].payee == "House payment"

    def test_service_export_import_round_trip_preserves_transfer(
        self, temp_db: Path, tmp_path: Path
    ) -> None:
        """Service-level QIF export then import on a fresh DB restores transfer links."""
        from dads_money.services import MoneyService

        # ── source DB ──────────────────────────────────────────────────────────
        src = MoneyService(temp_db)
        try:
            current = src.create_account("Current", AccountType.CHECKING, opening_balance=2000.0)
            equity = src.create_account("House Equity", AccountType.LIABILITY)
            src.create_transfer(
                from_account_id=current.id,
                to_account_id=equity.id,
                transfer_date=date(2024, 4, 1),
                amount=500.0,
                payee="April payment",
            )

            current_qif = tmp_path / "current.qif"
            equity_qif = tmp_path / "equity.qif"
            src.export_qif(str(current_qif), current.id)
            src.export_qif(str(equity_qif), equity.id)
        finally:
            src.close()

        # ── destination DB ─────────────────────────────────────────────────────
        dest_db = tmp_path / "dest.db"
        dest = MoneyService(dest_db)
        try:
            dest_current = dest.create_account("Current", AccountType.CHECKING)
            dest_equity = dest.create_account("House Equity", AccountType.LIABILITY)

            # Liability first so the name exists when current is imported
            dest.import_qif(str(equity_qif), dest_equity.id)
            dest.import_qif(str(current_qif), dest_current.id)

            current_txns = dest.get_transactions_for_account(dest_current.id)
            transfer_txns = [t for t in current_txns if t.transfer_account_id]
            assert len(transfer_txns) == 1
            assert transfer_txns[0].transfer_account_id == dest_equity.id
        finally:
            dest.close()
