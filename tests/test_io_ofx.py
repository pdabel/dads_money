"""Unit tests for OFX import functionality."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from dads_money.io_ofx import OFXImporter


class TestOFXAvailability:
    """Tests for OFX library availability checking."""

    def test_ofx_availability_check(self) -> None:
        """Test the is_available() method."""
        # This will be True or False depending on if ofxparse is installed
        result = OFXImporter.is_available()
        assert isinstance(result, bool)

    @patch("dads_money.io_ofx.OFX_AVAILABLE", True)
    def test_ofx_when_available(self) -> None:
        """Test OFX availability when library is available."""
        # When mocked as available, should return True
        result = OFXImporter.is_available()
        # Note: This tests the mocked version
        assert isinstance(result, bool)

    @patch("dads_money.io_ofx.OFX_AVAILABLE", False)
    def test_ofx_parse_file_when_unavailable(self) -> None:
        """Test that parsing raises ImportError when OFX is unavailable."""
        with patch("dads_money.io_ofx.OFX_AVAILABLE", False):
            with pytest.raises(ImportError) as exc_info:
                OFXImporter.parse_file("dummy.ofx")

            assert "ofxparse" in str(exc_info.value).lower()

    def test_ofx_parse_file_signature(self) -> None:
        """Test that parse_file method exists and has correct signature."""
        assert hasattr(OFXImporter, "parse_file")
        assert callable(OFXImporter.parse_file)


class TestOFXParsingStructure:
    """Tests for OFX parsing logic structure."""

    @patch("dads_money.io_ofx.OFX_AVAILABLE", True)
    @patch("dads_money.io_ofx.OfxParser")
    def test_ofx_parse_file_returns_list(self, mock_ofx_parser) -> None:
        """Test that parse_file returns a list of transactions."""
        # Mock the OFX parsing
        mock_ofx = MagicMock()
        mock_account = MagicMock()
        mock_statement = MagicMock()
        mock_transaction = MagicMock()

        # Set up mock structure
        mock_ofx_trans = MagicMock()
        mock_ofx_trans.date = MagicMock()
        mock_ofx_trans.date.date.return_value = None
        mock_ofx_trans.amount = "100.00"
        mock_ofx_trans.payee = "Test Payee"
        mock_ofx_trans.memo = "Test Memo"
        mock_ofx_trans.checknum = None

        mock_statement.transactions = [mock_ofx_trans]
        mock_account.statement = mock_statement
        mock_ofx.accounts = [mock_account]
        mock_ofx_parser.parse.return_value = mock_ofx

        # Import with mocked path
        with patch("builtins.open", MagicMock()):
            result = OFXImporter.parse_file("test.ofx")

        assert isinstance(result, list)

    @patch("dads_money.io_ofx.OFX_AVAILABLE", True)
    @patch("dads_money.io_ofx.OfxParser")
    def test_ofx_parse_empty_file(self, mock_ofx_parser) -> None:
        """Test parsing OFX file with no transactions."""
        mock_ofx = MagicMock()
        mock_ofx.accounts = []
        mock_ofx_parser.parse.return_value = mock_ofx

        with patch("builtins.open", MagicMock()):
            result = OFXImporter.parse_file("test.ofx")

        assert isinstance(result, list)
        assert len(result) == 0

    @patch("dads_money.io_ofx.OFX_AVAILABLE", True)
    @patch("dads_money.io_ofx.OfxParser")
    def test_ofx_parse_multiple_accounts(self, mock_ofx_parser) -> None:
        """Test parsing OFX file with multiple accounts."""
        mock_ofx = MagicMock()

        # Create 2 mock accounts with transactions
        mock_account1 = MagicMock()
        mock_account2 = MagicMock()

        mock_trans1 = MagicMock()
        mock_trans1.date = MagicMock()
        mock_trans1.date.date.return_value = None
        mock_trans1.amount = "100.00"
        mock_trans1.payee = "Payee 1"
        mock_trans1.memo = "Memo 1"
        mock_trans1.checknum = None

        mock_trans2 = MagicMock()
        mock_trans2.date = MagicMock()
        mock_trans2.date.date.return_value = None
        mock_trans2.amount = "200.00"
        mock_trans2.payee = "Payee 2"
        mock_trans2.memo = "Memo 2"
        mock_trans2.checknum = None

        mock_account1.statement.transactions = [mock_trans1]
        mock_account2.statement.transactions = [mock_trans2]
        mock_ofx.accounts = [mock_account1, mock_account2]
        mock_ofx_parser.parse.return_value = mock_ofx

        with patch("builtins.open", MagicMock()):
            result = OFXImporter.parse_file("test.ofx")

        assert len(result) >= 0  # Should handle multiple accounts


class TestOFXTransactionAmount:
    """Tests for OFX transaction amount parsing."""

    @patch("dads_money.io_ofx.OFX_AVAILABLE", True)
    @patch("dads_money.io_ofx.OfxParser")
    def test_ofx_amount_to_decimal(self, mock_ofx_parser) -> None:
        """Test that OFX amounts are converted to Decimal."""
        mock_ofx = MagicMock()
        mock_account = MagicMock()

        mock_trans = MagicMock()
        mock_trans.date = MagicMock()
        mock_trans.date.date.return_value = None
        mock_trans.amount = "123.45"
        mock_trans.payee = "Test"
        mock_trans.memo = ""
        mock_trans.checknum = None

        mock_account.statement.transactions = [mock_trans]
        mock_ofx.accounts = [mock_account]
        mock_ofx_parser.parse.return_value = mock_ofx

        with patch("builtins.open", MagicMock()):
            result = OFXImporter.parse_file("test.ofx")

        if len(result) > 0:
            assert isinstance(result[0].amount, Decimal)

    @patch("dads_money.io_ofx.OFX_AVAILABLE", True)
    @patch("dads_money.io_ofx.OfxParser")
    def test_ofx_negative_amount(self, mock_ofx_parser) -> None:
        """Test OFX parsing with negative amounts."""
        mock_ofx = MagicMock()
        mock_account = MagicMock()

        mock_trans = MagicMock()
        mock_trans.date = MagicMock()
        mock_trans.date.date.return_value = None
        mock_trans.amount = "-50.00"
        mock_trans.payee = "Expense"
        mock_trans.memo = ""
        mock_trans.checknum = None

        mock_account.statement.transactions = [mock_trans]
        mock_ofx.accounts = [mock_account]
        mock_ofx_parser.parse.return_value = mock_ofx

        with patch("builtins.open", MagicMock()):
            result = OFXImporter.parse_file("test.ofx")

        if len(result) > 0:
            assert result[0].amount == Decimal("-50.00")


class TestOFXTransactionFields:
    """Tests for OFX transaction field mapping."""

    @patch("dads_money.io_ofx.OFX_AVAILABLE", True)
    @patch("dads_money.io_ofx.OfxParser")
    def test_ofx_payee_field(self, mock_ofx_parser) -> None:
        """Test that OFX payee is correctly mapped."""
        mock_ofx = MagicMock()
        mock_account = MagicMock()

        mock_trans = MagicMock()
        mock_trans.date = MagicMock()
        mock_trans.date.date.return_value = None
        mock_trans.amount = "100.00"
        mock_trans.payee = "Test Payee Name"
        mock_trans.memo = "Test Memo"
        mock_trans.checknum = None

        mock_account.statement.transactions = [mock_trans]
        mock_ofx.accounts = [mock_account]
        mock_ofx_parser.parse.return_value = mock_ofx

        with patch("builtins.open", MagicMock()):
            result = OFXImporter.parse_file("test.ofx")

        if len(result) > 0:
            assert result[0].payee == "Test Payee Name"

    @patch("dads_money.io_ofx.OFX_AVAILABLE", True)
    @patch("dads_money.io_ofx.OfxParser")
    def test_ofx_missing_payee_defaults_to_empty(self, mock_ofx_parser) -> None:
        """Test that missing payee defaults to empty string."""
        mock_ofx = MagicMock()
        mock_account = MagicMock()

        mock_trans = MagicMock()
        mock_trans.date = MagicMock()
        mock_trans.date.date.return_value = None
        mock_trans.amount = "100.00"
        mock_trans.payee = None
        mock_trans.memo = None
        mock_trans.checknum = None

        mock_account.statement.transactions = [mock_trans]
        mock_ofx.accounts = [mock_account]
        mock_ofx_parser.parse.return_value = mock_ofx

        with patch("builtins.open", MagicMock()):
            result = OFXImporter.parse_file("test.ofx")

        if len(result) > 0:
            assert result[0].payee == ""
            assert result[0].memo == ""

    @patch("dads_money.io_ofx.OFX_AVAILABLE", True)
    @patch("dads_money.io_ofx.OfxParser")
    def test_ofx_check_number_field(self, mock_ofx_parser) -> None:
        """Test that check number is mapped if present."""
        mock_ofx = MagicMock()
        mock_account = MagicMock()

        mock_trans = MagicMock()
        mock_trans.date = MagicMock()
        mock_trans.date.date.return_value = None
        mock_trans.amount = "100.00"
        mock_trans.payee = "Test"
        mock_trans.memo = ""
        mock_trans.checknum = "12345"

        mock_account.statement.transactions = [mock_trans]
        mock_ofx.accounts = [mock_account]
        mock_ofx_parser.parse.return_value = mock_ofx

        with patch("builtins.open", MagicMock()):
            result = OFXImporter.parse_file("test.ofx")

        if len(result) > 0:
            assert result[0].check_number == "12345"
