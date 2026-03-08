"""Unit tests for storage layer."""

from datetime import date, datetime
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
from dads_money.storage import Storage


class TestAccountStorage:
    """Tests for account persistence."""

    def test_save_and_retrieve_account(self, storage: Storage) -> None:
        """Test saving and retrieving an account."""
        account = Account(
            name="Test Checking",
            account_type=AccountType.CHECKING,
            opening_balance=Decimal("1000.00"),
            current_balance=Decimal("1000.00"),
        )
        storage.save_account(account)

        retrieved = storage.get_account(account.id)
        assert retrieved is not None
        assert retrieved.name == "Test Checking"
        assert retrieved.account_type == AccountType.CHECKING
        assert retrieved.opening_balance == Decimal("1000.00")

    def test_save_account_with_all_fields(self, storage: Storage) -> None:
        """Test saving account with all optional fields."""
        account = Account(
            name="Complete Account",
            account_type=AccountType.SAVINGS,
            opening_balance=Decimal("5000.00"),
            current_balance=Decimal("5500.00"),
            description="Test savings account",
            account_number="123456789",
            institution="Test Bank",
        )
        storage.save_account(account)

        retrieved = storage.get_account(account.id)
        assert retrieved.description == "Test savings account"
        assert retrieved.account_number == "123456789"
        assert retrieved.institution == "Test Bank"

    def test_update_account(self, storage: Storage) -> None:
        """Test updating an existing account."""
        account = Account(
            name="Initial Name",
            account_type=AccountType.CHECKING,
            opening_balance=Decimal("1000.00"),
        )
        storage.save_account(account)

        # Update the account
        account.name = "Updated Name"
        account.current_balance = Decimal("1500.00")
        storage.save_account(account)

        retrieved = storage.get_account(account.id)
        assert retrieved.name == "Updated Name"
        assert retrieved.current_balance == Decimal("1500.00")

    def test_get_all_accounts(self, storage: Storage) -> None:
        """Test retrieving all accounts."""
        acc1 = Account(name="Account 1", account_type=AccountType.CHECKING)
        acc2 = Account(name="Account 2", account_type=AccountType.SAVINGS)
        storage.save_account(acc1)
        storage.save_account(acc2)

        accounts = storage.get_all_accounts()
        assert len(accounts) >= 2
        assert any(a.name == "Account 1" for a in accounts)
        assert any(a.name == "Account 2" for a in accounts)

    def test_delete_account(self, storage: Storage) -> None:
        """Test deleting an account."""
        account = Account(name="To Delete", account_type=AccountType.CHECKING)
        storage.save_account(account)

        storage.delete_account(account.id)
        retrieved = storage.get_account(account.id)
        assert retrieved is None

    def test_account_closed_flag(self, storage: Storage) -> None:
        """Test the closed flag for accounts."""
        account = Account(name="Active", account_type=AccountType.CHECKING, closed=False)
        storage.save_account(account)

        # Get without including closed
        accounts = storage.get_all_accounts(include_closed=False)
        assert any(a.id == account.id for a in accounts)

        # Close the account
        account.closed = True
        storage.save_account(account)

        accounts = storage.get_all_accounts(include_closed=False)
        assert not any(a.id == account.id for a in accounts)

        # Get including closed
        accounts = storage.get_all_accounts(include_closed=True)
        assert any(a.id == account.id for a in accounts)


class TestCategoryStorage:
    """Tests for category persistence."""

    def test_save_and_retrieve_category(self, storage: Storage) -> None:
        """Test saving and retrieving a category."""
        category = Category(name="Groceries", is_income=False)
        storage.save_category(category)

        retrieved = storage.get_category(category.id)
        assert retrieved is not None
        assert retrieved.name == "Groceries"
        assert retrieved.is_income is False

    def test_category_with_properties(self, storage: Storage) -> None:
        """Test saving category with all properties."""
        category = Category(
            name="Medical Expenses",
            is_income=False,
            is_tax_related=True,
            description="Healthcare-related expenses",
        )
        storage.save_category(category)

        retrieved = storage.get_category(category.id)
        assert retrieved.is_tax_related is True
        assert retrieved.description == "Healthcare-related expenses"

    def test_save_income_category(self, storage: Storage) -> None:
        """Test saving income category."""
        category = Category(name="Salary", is_income=True)
        storage.save_category(category)

        retrieved = storage.get_category(category.id)
        assert retrieved.is_income is True

    def test_get_all_categories(self, storage: Storage) -> None:
        """Test retrieving all categories."""
        cat1 = Category(name="Food", is_income=False)
        cat2 = Category(name="Salary", is_income=True)
        storage.save_category(cat1)
        storage.save_category(cat2)

        categories = storage.get_all_categories()
        assert len(categories) >= 2
        assert any(c.name == "Food" for c in categories)
        assert any(c.name == "Salary" for c in categories)

    def test_delete_category(self, storage: Storage) -> None:
        """Test deleting a category."""
        category = Category(name="Temporary", is_income=False)
        storage.save_category(category)

        storage.delete_category(category.id)
        retrieved = storage.get_category(category.id)
        assert retrieved is None

    def test_update_category(self, storage: Storage) -> None:
        """Test updating a category."""
        category = Category(name="Original", is_income=False)
        storage.save_category(category)

        category.name = "Updated"
        category.is_tax_related = True
        storage.save_category(category)

        retrieved = storage.get_category(category.id)
        assert retrieved.name == "Updated"
        assert retrieved.is_tax_related is True


class TestTransactionStorage:
    """Tests for transaction persistence."""

    def test_save_and_retrieve_transaction(
        self, storage: Storage, sample_account: Account, sample_category: Category
    ) -> None:
        """Test saving and retrieving a transaction."""
        txn = Transaction(
            account_id=sample_account.id,
            payee="Coffee Shop",
            amount=Decimal("-4.50"),
            category_id=sample_category.id,
        )
        storage.save_transaction(txn)

        retrieved = storage.get_transaction(txn.id)
        assert retrieved is not None
        assert retrieved.payee == "Coffee Shop"
        assert retrieved.amount == Decimal("-4.50")
        assert retrieved.category_id == sample_category.id

    def test_transaction_with_all_fields(self, storage: Storage, sample_account: Account) -> None:
        """Test saving transaction with all fields."""
        txn = Transaction(
            account_id=sample_account.id,
            date=date(2024, 3, 15),
            payee="Test Payee",
            amount=Decimal("100.00"),
            memo="Test memo",
            check_number="12345",
            status=TransactionStatus.CLEARED,
        )
        storage.save_transaction(txn)

        retrieved = storage.get_transaction(txn.id)
        assert retrieved.date == date(2024, 3, 15)
        assert retrieved.check_number == "12345"
        assert retrieved.status == TransactionStatus.CLEARED
        assert retrieved.memo == "Test memo"

    def test_get_transactions_for_account(self, storage: Storage, sample_account: Account) -> None:
        """Test retrieving all transactions for an account."""
        txn1 = Transaction(
            account_id=sample_account.id,
            payee="Payee 1",
            amount=Decimal("50.00"),
        )
        txn2 = Transaction(
            account_id=sample_account.id,
            payee="Payee 2",
            amount=Decimal("-25.00"),
        )
        storage.save_transaction(txn1)
        storage.save_transaction(txn2)

        transactions = storage.get_transactions_for_account(sample_account.id)
        assert len(transactions) >= 2
        payees = {t.payee for t in transactions}
        assert "Payee 1" in payees
        assert "Payee 2" in payees

    def test_update_transaction(self, storage: Storage, sample_account: Account) -> None:
        """Test updating a transaction."""
        txn = Transaction(account_id=sample_account.id, payee="Original", amount=Decimal("100.00"))
        storage.save_transaction(txn)

        txn.payee = "Updated"
        txn.amount = Decimal("150.00")
        storage.save_transaction(txn)

        retrieved = storage.get_transaction(txn.id)
        assert retrieved.payee == "Updated"
        assert retrieved.amount == Decimal("150.00")

    def test_delete_transaction(self, storage: Storage, sample_account: Account) -> None:
        """Test deleting a transaction."""
        txn = Transaction(
            account_id=sample_account.id,
            payee="To Delete",
            amount=Decimal("50.00"),
        )
        storage.save_transaction(txn)

        storage.delete_transaction(txn.id, sample_account.id)
        retrieved = storage.get_transaction(txn.id)
        assert retrieved is None

    def test_transaction_with_splits(
        self,
        storage: Storage,
        sample_account: Account,
        sample_category: Category,
    ) -> None:
        """Test saving transaction with splits."""
        split1 = Split(category_id=sample_category.id, amount=Decimal("60.00"))
        split2 = Split(category_id=sample_category.id, amount=Decimal("40.00"))

        txn = Transaction(
            account_id=sample_account.id,
            payee="Split Transaction",
            amount=Decimal("100.00"),
            splits=[split1, split2],
        )
        storage.save_transaction(txn)

        retrieved = storage.get_transaction(txn.id)
        assert len(retrieved.splits) == 2
        amounts = {s.amount for s in retrieved.splits}
        assert Decimal("60.00") in amounts
        assert Decimal("40.00") in amounts

    def test_transaction_status_preserved(self, storage: Storage, sample_account: Account) -> None:
        """Test that transaction status is preserved."""
        for status in [
            TransactionStatus.UNCLEARED,
            TransactionStatus.CLEARED,
            TransactionStatus.RECONCILED,
        ]:
            txn = Transaction(
                account_id=sample_account.id,
                payee=f"Status {status.value}",
                amount=Decimal("10.00"),
                status=status,
            )
            storage.save_transaction(txn)

            retrieved = storage.get_transaction(txn.id)
            assert retrieved.status == status


class TestDecimalPreservation:
    """Tests for Decimal type preservation in storage."""

    def test_account_balance_decimal_precision(self, storage: Storage) -> None:
        """Test that Decimal precision is preserved for account balances."""
        account = Account(
            name="Precision Test",
            account_type=AccountType.CHECKING,
            opening_balance=Decimal("1234.56"),
            current_balance=Decimal("9999.99"),
        )
        storage.save_account(account)

        retrieved = storage.get_account(account.id)
        assert isinstance(retrieved.opening_balance, Decimal)
        assert isinstance(retrieved.current_balance, Decimal)
        assert retrieved.opening_balance == Decimal("1234.56")
        assert retrieved.current_balance == Decimal("9999.99")

    def test_transaction_amount_decimal_precision(
        self, storage: Storage, sample_account: Account
    ) -> None:
        """Test that transaction amounts preserve Decimal precision."""
        amounts = [
            Decimal("0.01"),
            Decimal("100.00"),
            Decimal("9999.99"),
            Decimal("-50.25"),
        ]

        for amount in amounts:
            txn = Transaction(
                account_id=sample_account.id,
                payee=f"Amount {amount}",
                amount=amount,
            )
            storage.save_transaction(txn)

            retrieved = storage.get_transaction(txn.id)
            assert isinstance(retrieved.amount, Decimal)
            assert retrieved.amount == amount
