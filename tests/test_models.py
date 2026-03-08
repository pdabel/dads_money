"""Unit tests for data models."""

from datetime import date
from decimal import Decimal

import pytest

from dads_money.models import (
    Account,
    AccountType,
    Category,
    Split,
    Transaction,
    TransactionStatus,
)


class TestAccount:
    """Tests for Account model."""

    def test_account_creation(self) -> None:
        """Test creating an account with default values."""
        account = Account(name="Test Account", account_type=AccountType.CHECKING)
        assert account.name == "Test Account"
        assert account.account_type == AccountType.CHECKING
        assert account.opening_balance == Decimal("0.00")
        assert account.current_balance == Decimal("0.00")

    def test_account_decimal_conversion(self) -> None:
        """Test that account balances are converted to Decimal."""
        account = Account(
            name="Test",
            account_type=AccountType.SAVINGS,
            opening_balance=100.5,
            current_balance=200.75,
        )
        assert isinstance(account.opening_balance, Decimal)
        assert isinstance(account.current_balance, Decimal)
        assert account.opening_balance == Decimal("100.5")
        assert account.current_balance == Decimal("200.75")


class TestTransaction:
    """Tests for Transaction model."""

    def test_transaction_creation(self) -> None:
        """Test creating a transaction."""
        txn = Transaction(
            account_id="acc1",
            payee="Test Payee",
            amount=Decimal("50.00"),
        )
        assert txn.account_id == "acc1"
        assert txn.payee == "Test Payee"
        assert txn.amount == Decimal("50.00")
        assert txn.status == TransactionStatus.UNCLEARED

    def test_transaction_decimal_conversion(self) -> None:
        """Test that transaction amounts are converted to Decimal."""
        txn = Transaction(account_id="acc1", payee="Test", amount=123.45)
        assert isinstance(txn.amount, Decimal)
        assert txn.amount == Decimal("123.45")

    def test_transaction_is_split(self) -> None:
        """Test checking if transaction has splits."""
        txn = Transaction(account_id="acc1", amount=Decimal("100.00"))
        assert txn.is_split() is False

        split = Split(category_id="cat1", amount=Decimal("100.00"))
        txn.splits.append(split)
        assert txn.is_split() is True

    def test_validate_splits(self) -> None:
        """Test split validation."""
        txn = Transaction(account_id="acc1", amount=Decimal("100.00"))
        # No splits - validation should pass
        assert txn.validate_splits() is True

        # Add matching split
        split = Split(category_id="cat1", amount=Decimal("100.00"))
        txn.splits.append(split)
        assert txn.validate_splits() is True

        # Add non-matching split
        txn.splits.append(Split(category_id="cat2", amount=Decimal("50.00")))
        assert txn.validate_splits() is False


class TestCategory:
    """Tests for Category model."""

    def test_category_creation(self) -> None:
        """Test creating a category."""
        cat = Category(name="Groceries", is_income=False)
        assert cat.name == "Groceries"
        assert cat.is_income is False

    def test_category_full_name_no_parent(self) -> None:
        """Test full name for category without parent."""
        cat = Category(name="Utilities", is_income=False)
        assert cat.full_name() == "Utilities"

    def test_category_full_name_with_parent(self) -> None:
        """Test full name for subcategory."""
        parent = Category(name="Auto", parent_id=None)
        child = Category(name="Gas", parent_id=parent.id)
        categories = {parent.id: parent}
        assert child.full_name(categories) == "Auto:Gas"


class TestSplit:
    """Tests for Split model."""

    def test_split_creation(self) -> None:
        """Test creating a split."""
        split = Split(category_id="cat1", amount=Decimal("50.00"))
        assert split.category_id == "cat1"
        assert split.amount == Decimal("50.00")

    def test_split_decimal_conversion(self) -> None:
        """Test that split amounts are converted to Decimal."""
        split = Split(category_id="cat1", amount=75.25)
        assert isinstance(split.amount, Decimal)
        assert split.amount == Decimal("75.25")
