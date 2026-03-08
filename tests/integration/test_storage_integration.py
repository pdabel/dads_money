"""Integration tests for complete workflows."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from dads_money.models import AccountType, TransactionStatus
from dads_money.services import MoneyService


class TestCompleteWorkflow:
    """Tests for complete application workflows."""

    def test_create_account_add_transactions_retrieve(self, temp_db: Path) -> None:
        """Test complete workflow: create account → add transactions → retrieve."""
        service = MoneyService(temp_db)
        try:
            # Create account
            account = service.create_account(
                name="Checking",
                account_type=AccountType.CHECKING,
                opening_balance=1000.0,
            )

            # Create category
            category = service.create_category("Groceries")

            # Add transactions
            txn1 = service.create_transaction(
                account_id=account.id,
                date=date(2024, 3, 1),
                amount=-50.0,
                payee="Grocery Store",
                category_id=category.id,
            )

            txn2 = service.create_transaction(
                account_id=account.id,
                date=date(2024, 3, 2),
                amount=-25.0,
                payee="Gas Station",
            )

            # Retrieve and verify
            transactions = service.get_transactions_for_account(account.id)
            assert len(transactions) >= 2

            payees = {t.payee for t in transactions}
            assert "Grocery Store" in payees
            assert "Gas Station" in payees

            # Verify transaction details
            grocery_txn = next(t for t in transactions if t.payee == "Grocery Store")
            assert grocery_txn.category_id == category.id
        finally:
            service.close()

    def test_import_qif_and_retrieve(self, temp_db: Path) -> None:
        """Test importing QIF file and retrieving transactions."""
        service = MoneyService(temp_db)
        try:
            # Create account
            account = service.create_account(name="Test Account", account_type=AccountType.CHECKING)

            # Create QIF content
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
            with NamedTemporaryFile(mode="w", suffix=".qif", delete=False, newline="") as f:
                f.write(qif_content)
                qif_file = Path(f.name)

            try:
                # Import transactions
                count = service.import_qif(str(qif_file), account.id)
                assert count > 0

                # Retrieve and verify
                transactions = service.get_transactions_for_account(account.id)
                assert len(transactions) > 0

                payees = {t.payee for t in transactions}
                assert "Grocery Store" in payees or "Bonus" in payees
            finally:
                qif_file.unlink(missing_ok=True)
        finally:
            service.close()

    def test_import_csv_and_export_qif(self, temp_db: Path) -> None:
        """Test importing CSV and exporting to QIF."""
        service = MoneyService(temp_db)
        try:
            # Create account
            account = service.create_account(name="Test Account", account_type=AccountType.CHECKING)

            # Create CSV content
            csv_content = """Date,Payee,Amount,Memo
2024-03-15,-50.00,Grocery Store,Weekly shopping
2024-03-16,150.00,Bonus,Quarterly bonus
"""
            with NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
                f.write(csv_content)
                csv_file = Path(f.name)

            try:
                # Import from CSV
                count = service.import_csv(str(csv_file), account.id)
                assert count > 0

                # Export to QIF
                with NamedTemporaryFile(suffix=".qif", delete=False) as f:
                    qif_file = Path(f.name)

                try:
                    service.export_qif(str(qif_file), account.id)

                    # Verify QIF file was created
                    assert qif_file.exists()
                    assert qif_file.stat().st_size > 0
                finally:
                    qif_file.unlink(missing_ok=True)
            finally:
                csv_file.unlink(missing_ok=True)
        finally:
            service.close()

    def test_multiple_accounts_with_transfers_concept(self, temp_db: Path) -> None:
        """Test managing multiple accounts."""
        service = MoneyService(temp_db)
        try:
            # Create multiple accounts
            checking = service.create_account("Checking", AccountType.CHECKING, 1000.0)
            savings = service.create_account("Savings", AccountType.SAVINGS, 5000.0)

            # Add transactions to both
            service.create_transaction(
                account_id=checking.id,
                date=date.today(),
                amount=-100.0,
                payee="ATM Withdrawal",
            )

            service.create_transaction(
                account_id=savings.id,
                date=date.today(),
                amount=500.0,
                payee="Interest",
            )

            # Verify separate transactions
            checking_txns = service.get_transactions_for_account(checking.id)
            savings_txns = service.get_transactions_for_account(savings.id)

            # Each should have their transactions
            assert len(checking_txns) > 0
            assert len(savings_txns) > 0

            checking_payees = {t.payee for t in checking_txns}
            savings_payees = {t.payee for t in savings_txns}

            assert "ATM Withdrawal" in checking_payees
            assert "Interest" in savings_payees
        finally:
            service.close()

    def test_category_hierarchy(self, temp_db: Path) -> None:
        """Test creating and using category hierarchy."""
        service = MoneyService(temp_db)
        try:
            # Create parent category
            auto = service.create_category("Auto", is_income=False)

            # Create subcategories
            gas = service.create_category("Gas", is_income=False, parent_id=auto.id)
            insurance = service.create_category("Insurance", is_income=False, parent_id=auto.id)

            # Create account and transactions
            account = service.create_account("Test", AccountType.CHECKING, opening_balance=1000.0)

            service.create_transaction(
                account_id=account.id,
                date=date.today(),
                amount=-50.0,
                payee="Gas Station",
                category_id=gas.id,
            )

            service.create_transaction(
                account_id=account.id,
                date=date.today(),
                amount=-100.0,
                payee="Insurance Co",
                category_id=insurance.id,
            )

            # Retrieve and verify
            transactions = service.get_transactions_for_account(account.id)
            assert len(transactions) >= 2

            gas_txn = next((t for t in transactions if t.category_id == gas.id), None)
            assert gas_txn is not None

            insurance_txn = next((t for t in transactions if t.category_id == insurance.id), None)
            assert insurance_txn is not None
        finally:
            service.close()

    def test_transaction_lifecycle(self, temp_db: Path) -> None:
        """Test complete transaction lifecycle: create → update → retrieve."""
        service = MoneyService(temp_db)
        try:
            account = service.create_account("Test", AccountType.CHECKING, opening_balance=1000.0)

            # Create
            txn = service.create_transaction(
                account_id=account.id,
                date=date(2024, 3, 1),
                amount=-50.0,
                payee="Original Payee",
                status=TransactionStatus.UNCLEARED,
            )
            txn_id = txn.id

            # Verify created
            retrieved1 = service.get_transaction(txn_id)
            assert retrieved1.payee == "Original Payee"
            assert retrieved1.status == TransactionStatus.UNCLEARED

            # Update
            retrieved1.payee = "Updated Payee"
            retrieved1.status = TransactionStatus.CLEARED
            service.update_transaction(retrieved1)

            # Verify updated
            retrieved2 = service.get_transaction(txn_id)
            assert retrieved2.payee == "Updated Payee"
            assert retrieved2.status == TransactionStatus.CLEARED

            # Delete
            service.delete_transaction(txn_id, account.id)

            # Verify deleted
            retrieved3 = service.get_transaction(txn_id)
            assert retrieved3 is None
        finally:
            service.close()

    def test_payee_management_workflow(self, temp_db: Path) -> None:
        """Test payee management and retrieval."""
        service = MoneyService(temp_db)
        try:
            account = service.create_account("Test", AccountType.CHECKING)

            # Add transactions with various payees
            service.create_transaction(
                account_id=account.id,
                date=date.today(),
                amount=-25.0,
                payee="Favorite Coffee Shop",
            )

            service.create_transaction(
                account_id=account.id,
                date=date.today(),
                amount=-50.0,
                payee="Regular Restaurant",
            )

            # Add predefined payee
            service.add_payee("Favorite Coffee Shop")

            # Get all payees (should include transaction and predefined)
            all_payees = service.get_all_payees()
            assert "Favorite Coffee Shop" in all_payees
            assert "Regular Restaurant" in all_payees

            # Get predefined payees
            predefined = service.get_predefined_payees()
            assert "Favorite Coffee Shop" in predefined

            # Delete predefined payee
            service.delete_payee("Favorite Coffee Shop")

            predefined_after = service.get_predefined_payees()
            assert "Favorite Coffee Shop" not in predefined_after
        finally:
            service.close()

    def test_export_import_roundtrip(self, temp_db: Path) -> None:
        """Test exporting and re-importing transactions."""
        service = MoneyService(temp_db)
        try:
            # Create account and transactions
            account = service.create_account("Test", AccountType.CHECKING)

            service.create_transaction(
                account_id=account.id,
                date=date(2024, 3, 1),
                amount=-50.0,
                payee="Payee 1",
                memo="Memo 1",
            )

            service.create_transaction(
                account_id=account.id,
                date=date(2024, 3, 2),
                amount=100.0,
                payee="Payee 2",
                memo="Memo 2",
            )

            original_txns = service.get_transactions_for_account(account.id)
            original_count = len(original_txns)

            # Export to CSV
            with NamedTemporaryFile(suffix=".csv", delete=False) as f:
                csv_file = Path(f.name)

            try:
                service.export_csv(str(csv_file), account.id)

                # Create new account
                account2 = service.create_account("Imported", AccountType.SAVINGS)

                # Re-import
                imported_count = service.import_csv(str(csv_file), account2.id)
                assert imported_count > 0

                # Verify re-imported transactions
                reimported_txns = service.get_transactions_for_account(account2.id)
                assert len(reimported_txns) >= imported_count
            finally:
                csv_file.unlink(missing_ok=True)
        finally:
            service.close()
