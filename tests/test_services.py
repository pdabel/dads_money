"""Unit tests for service layer."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from dads_money.models import AccountType, TransactionStatus
from dads_money.services import MoneyService


class TestAccountServices:
    """Tests for account service methods."""

    def test_create_account(self, temp_db: Path) -> None:
        """Test creating an account via service."""
        service = MoneyService(temp_db)
        try:
            account = service.create_account(
                name="Test Checking",
                account_type=AccountType.CHECKING,
                opening_balance=1000.0,
            )

            assert account.id is not None
            assert account.name == "Test Checking"
            assert account.account_type == AccountType.CHECKING
            assert account.opening_balance == Decimal("1000.0")

            # Verify it's persisted
            retrieved = service.get_account(account.id)
            assert retrieved is not None
            assert retrieved.name == "Test Checking"
        finally:
            service.close()

    def test_create_multiple_account_types(self, temp_db: Path) -> None:
        """Test creating accounts of different types."""
        service = MoneyService(temp_db)
        try:
            types_to_test = [
                AccountType.CHECKING,
                AccountType.SAVINGS,
                AccountType.CREDIT_CARD,
                AccountType.CASH,
            ]

            for acc_type in types_to_test:
                account = service.create_account(
                    name=f"{acc_type.value} Account",
                    account_type=acc_type,
                )
                assert account.account_type == acc_type

                retrieved = service.get_account(account.id)
                assert retrieved.account_type == acc_type
        finally:
            service.close()

    def test_get_all_accounts(self, temp_db: Path) -> None:
        """Test retrieving all accounts."""
        service = MoneyService(temp_db)
        try:
            acc1 = service.create_account("Account 1", AccountType.CHECKING, 1000.0)
            acc2 = service.create_account("Account 2", AccountType.SAVINGS, 2000.0)

            accounts = service.get_all_accounts()
            assert len(accounts) >= 2
            ids = {a.id for a in accounts}
            assert acc1.id in ids
            assert acc2.id in ids
        finally:
            service.close()

    def test_update_account(self, temp_db: Path) -> None:
        """Test updating an account via service."""
        service = MoneyService(temp_db)
        try:
            account = service.create_account("Original Name", AccountType.CHECKING, 1000.0)

            account.name = "Updated Name"
            account.current_balance = Decimal("1500.0")
            service.update_account(account)

            retrieved = service.get_account(account.id)
            assert retrieved.name == "Updated Name"
            assert retrieved.current_balance == Decimal("1500.0")
        finally:
            service.close()

    def test_delete_account(self, temp_db: Path) -> None:
        """Test deleting an account via service."""
        service = MoneyService(temp_db)
        try:
            account = service.create_account("To Delete", AccountType.CHECKING)
            account_id = account.id

            service.delete_account(account_id)

            retrieved = service.get_account(account_id)
            assert retrieved is None
        finally:
            service.close()


class TestCategoryServices:
    """Tests for category service methods."""

    def test_create_category(self, temp_db: Path) -> None:
        """Test creating a category via service."""
        service = MoneyService(temp_db)
        try:
            category = service.create_category("Groceries", is_income=False)

            assert category.id is not None
            assert category.name == "Groceries"
            assert category.is_income is False

            retrieved = service.get_category(category.id)
            assert retrieved.name == "Groceries"
        finally:
            service.close()

    def test_create_income_category(self, temp_db: Path) -> None:
        """Test creating an income category."""
        service = MoneyService(temp_db)
        try:
            category = service.create_category("Salary", is_income=True)
            assert category.is_income is True

            retrieved = service.get_category(category.id)
            assert retrieved.is_income is True
        finally:
            service.close()

    def test_get_all_categories(self, temp_db: Path) -> None:
        """Test retrieving all categories."""
        service = MoneyService(temp_db)
        try:
            cat1 = service.create_category("Food")
            cat2 = service.create_category("Utilities")

            categories = service.get_all_categories()
            assert len(categories) >= 2
            names = {c.name for c in categories}
            assert "Food" in names
            assert "Utilities" in names
        finally:
            service.close()

    def test_categories_dict(self, temp_db: Path) -> None:
        """Test getting categories as dictionary."""
        service = MoneyService(temp_db)
        try:
            cat1 = service.create_category("Category 1")
            cat2 = service.create_category("Category 2")

            cat_dict = service.get_categories_dict()
            assert cat1.id in cat_dict
            assert cat2.id in cat_dict
            assert cat_dict[cat1.id].name == "Category 1"
        finally:
            service.close()

    def test_update_category(self, temp_db: Path) -> None:
        """Test updating a category."""
        service = MoneyService(temp_db)
        try:
            category = service.create_category("Original")

            category.name = "Updated"
            category.is_tax_related = True
            service.update_category(category)

            retrieved = service.get_category(category.id)
            assert retrieved.name == "Updated"
            assert retrieved.is_tax_related is True
        finally:
            service.close()

    def test_delete_category(self, temp_db: Path) -> None:
        """Test deleting a category."""
        service = MoneyService(temp_db)
        try:
            category = service.create_category("To Delete")
            category_id = category.id

            service.delete_category(category_id)

            retrieved = service.get_category(category_id)
            assert retrieved is None
        finally:
            service.close()

    def test_category_cache_invalidation(self, temp_db: Path) -> None:
        """Test that category cache is invalidated on updates."""
        service = MoneyService(temp_db)
        try:
            cat = service.create_category("Original")

            # Cache is loaded
            cats1 = service.get_all_categories()
            assert any(c.id == cat.id for c in cats1)

            # Update should invalidate cache
            cat.name = "Updated"
            service.update_category(cat)

            cats2 = service.get_all_categories()
            assert any(c.name == "Updated" for c in cats2)
        finally:
            service.close()


class TestTransactionServices:
    """Tests for transaction service methods."""

    def test_create_transaction(self, temp_db: Path) -> None:
        """Test creating a transaction via service."""
        service = MoneyService(temp_db)
        try:
            account = service.create_account("Test", AccountType.CHECKING)
            category = service.create_category("Test Category")

            txn = service.create_transaction(
                account_id=account.id,
                date=date(2024, 3, 15),
                amount=50.0,
                payee="Test Payee",
                memo="Test memo",
            )

            assert txn.id is not None
            assert txn.payee == "Test Payee"
            assert txn.amount == Decimal("50.0")

            retrieved = service.get_transaction(txn.id)
            assert retrieved.payee == "Test Payee"
        finally:
            service.close()

    def test_transaction_status(self, temp_db: Path) -> None:
        """Test transaction status handling."""
        service = MoneyService(temp_db)
        try:
            account = service.create_account("Test", AccountType.CHECKING)

            # Default status should be UNCLEARED
            txn = service.create_transaction(account_id=account.id, date=date.today(), amount=10.0)
            assert txn.status == TransactionStatus.UNCLEARED

            # Set specific status
            txn2 = service.create_transaction(
                account_id=account.id,
                date=date.today(),
                amount=20.0,
                status=TransactionStatus.CLEARED,
            )
            retrieved = service.get_transaction(txn2.id)
            assert retrieved.status == TransactionStatus.CLEARED
        finally:
            service.close()

    def test_get_transactions_for_account(self, temp_db: Path) -> None:
        """Test retrieving transactions for specific account."""
        service = MoneyService(temp_db)
        try:
            acc1 = service.create_account("Account 1", AccountType.CHECKING)
            acc2 = service.create_account("Account 2", AccountType.SAVINGS)

            txn1 = service.create_transaction(
                account_id=acc1.id, date=date.today(), amount=50.0, payee="Payee 1"
            )
            txn2 = service.create_transaction(
                account_id=acc1.id, date=date.today(), amount=100.0, payee="Payee 2"
            )
            txn3 = service.create_transaction(
                account_id=acc2.id, date=date.today(), amount=75.0, payee="Payee 3"
            )

            acc1_txns = service.get_transactions_for_account(acc1.id)
            payees = {t.payee for t in acc1_txns}
            assert "Payee 1" in payees
            assert "Payee 2" in payees
            assert "Payee 3" not in payees
        finally:
            service.close()

    def test_update_transaction(self, temp_db: Path) -> None:
        """Test updating a transaction."""
        service = MoneyService(temp_db)
        try:
            account = service.create_account("Test", AccountType.CHECKING)

            txn = service.create_transaction(
                account_id=account.id,
                date=date(2024, 1, 1),
                amount=100.0,
                payee="Original",
            )

            txn.payee = "Updated"
            txn.amount = Decimal("150.0")
            service.update_transaction(txn)

            retrieved = service.get_transaction(txn.id)
            assert retrieved.payee == "Updated"
            assert retrieved.amount == Decimal("150.0")
            # Modified date should be updated
            assert retrieved.modified_date != txn.created_date
        finally:
            service.close()

    def test_delete_transaction(self, temp_db: Path) -> None:
        """Test deleting a transaction."""
        service = MoneyService(temp_db)
        try:
            account = service.create_account("Test", AccountType.CHECKING)

            txn = service.create_transaction(
                account_id=account.id,
                date=date.today(),
                amount=50.0,
                payee="To Delete",
            )

            service.delete_transaction(txn.id, account.id)

            retrieved = service.get_transaction(txn.id)
            assert retrieved is None
        finally:
            service.close()

    def test_negative_transaction(self, temp_db: Path) -> None:
        """Test creating transactions with negative amounts."""
        service = MoneyService(temp_db)
        try:
            account = service.create_account("Test", AccountType.CHECKING)

            txn = service.create_transaction(
                account_id=account.id,
                date=date.today(),
                amount=-50.0,
                payee="Withdrawal",
            )

            retrieved = service.get_transaction(txn.id)
            assert retrieved.amount == Decimal("-50.0")
        finally:
            service.close()


class TestPayeeServices:
    """Tests for payee operations."""

    def test_get_all_payees(self, temp_db: Path) -> None:
        """Test retrieving all payees from transactions."""
        service = MoneyService(temp_db)
        try:
            account = service.create_account("Test", AccountType.CHECKING)

            service.create_transaction(
                account_id=account.id,
                date=date.today(),
                amount=50.0,
                payee="Grocery Store",
            )
            service.create_transaction(
                account_id=account.id,
                date=date.today(),
                amount=25.0,
                payee="Gas Station",
            )

            payees = service.get_all_payees()
            assert "Grocery Store" in payees
            assert "Gas Station" in payees
        finally:
            service.close()

    def test_add_predefined_payee(self, temp_db: Path) -> None:
        """Test adding predefined payee."""
        service = MoneyService(temp_db)
        try:
            service.add_payee("Favorite Payee")

            payees = service.get_predefined_payees()
            assert "Favorite Payee" in payees
        finally:
            service.close()

    def test_delete_predefined_payee(self, temp_db: Path) -> None:
        """Test deleting predefined payee."""
        service = MoneyService(temp_db)
        try:
            service.add_payee("To Delete")
            payees = service.get_predefined_payees()
            assert "To Delete" in payees

            service.delete_payee("To Delete")
            payees = service.get_predefined_payees()
            assert "To Delete" not in payees
        finally:
            service.close()
