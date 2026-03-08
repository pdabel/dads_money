"""Application services layer."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .config import Config
from .io_csv import CSVParser, CSVWriter
from .io_ofx import OFXImporter
from .io_qif import QIFParser, QIFWriter
from .models import Account, Category, Transaction
from .storage import Storage


class MoneyService:
    """Main application service coordinating storage and business logic."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the service."""
        if db_path is None:
            db_path = Config.get_database_path()
        self.storage = Storage(db_path)
        self._categories_cache = None

    def close(self):
        """Close the service and underlying storage."""
        self.storage.close()

    # Account operations
    def create_account(
        self, name: str, account_type, opening_balance: float = 0.0, savings_subtype=None
    ) -> Account:
        """Create a new account."""
        account = Account(
            name=name,
            account_type=account_type,
            savings_subtype=savings_subtype,
            opening_balance=opening_balance,
            current_balance=opening_balance,
        )
        self.storage.save_account(account)
        return account

    def get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        return self.storage.get_account(account_id)

    def get_all_accounts(self, include_closed: bool = False) -> List[Account]:
        """Get all accounts."""
        return self.storage.get_all_accounts(include_closed)

    def update_account(self, account: Account):
        """Update an existing account."""
        self.storage.save_account(account)

    def delete_account(self, account_id: str):
        """Delete an account."""
        self.storage.delete_account(account_id)

    # Category operations
    def create_category(
        self, name: str, is_income: bool = False, parent_id: Optional[str] = None
    ) -> Category:
        """Create a new category."""
        category = Category(name=name, is_income=is_income, parent_id=parent_id)
        self.storage.save_category(category)
        self._categories_cache = None  # Invalidate cache
        return category

    def get_category(self, category_id: str) -> Optional[Category]:
        """Get category by ID."""
        return self.storage.get_category(category_id)

    def get_all_categories(self) -> List[Category]:
        """Get all categories (cached)."""
        if self._categories_cache is None:
            self._categories_cache = self.storage.get_all_categories()
        return self._categories_cache

    def get_categories_dict(self) -> dict:
        """Get categories as a dictionary keyed by ID."""
        return {cat.id: cat for cat in self.get_all_categories()}

    def update_category(self, category: Category):
        """Update an existing category."""
        self.storage.save_category(category)
        self._categories_cache = None

    def delete_category(self, category_id: str):
        """Delete a category."""
        self.storage.delete_category(category_id)
        self._categories_cache = None

    # Transaction operations
    def create_transaction(
        self,
        account_id: str,
        date,
        amount: float,
        payee: str = "",
        memo: str = "",
        check_number: str = "",
        status=None,
    ) -> Transaction:
        """Create a new transaction."""
        from .models import TransactionStatus

        transaction = Transaction(
            account_id=account_id,
            date=date,
            amount=amount,
            payee=payee,
            memo=memo,
            check_number=check_number,
            status=status if status is not None else TransactionStatus.UNCLEARED,
        )
        self.storage.save_transaction(transaction)
        return transaction

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Get transaction by ID."""
        return self.storage.get_transaction(transaction_id)

    def get_transactions_for_account(self, account_id: str) -> List[Transaction]:
        """Get all transactions for an account."""
        return self.storage.get_transactions_for_account(account_id)

    def update_transaction(self, transaction: Transaction):
        """Update an existing transaction."""
        transaction.modified_date = datetime.now()
        self.storage.save_transaction(transaction)

    def delete_transaction(self, transaction_id: str, account_id: str):
        """Delete a transaction."""
        self.storage.delete_transaction(transaction_id, account_id)

    # Import/Export operations
    def import_qif(self, file_path: str, account_id: str) -> int:
        """Import transactions from QIF file."""
        transactions = QIFParser.parse_file(file_path)
        count = 0
        for trans in transactions:
            trans.account_id = account_id
            self.storage.save_transaction(trans)
            count += 1
        return count

    def export_qif(self, file_path: str, account_id: str):
        """Export account transactions to QIF file."""
        transactions = self.get_transactions_for_account(account_id)
        account = self.get_account(account_id)

        # Determine QIF account type
        account_type_map = {
            "Current Account": "Bank",
            "Checking": "Bank",
            "Savings": "Bank",
            "Credit Card": "CCard",
            "Cash": "Cash",
        }
        qif_type = account_type_map.get(account.account_type.value, "Bank")

        QIFWriter.write_file(file_path, transactions, qif_type)

    def import_csv(self, file_path: str, account_id: str) -> int:
        """Import transactions from CSV file."""
        transactions = CSVParser.parse_file(file_path)
        count = 0
        for trans in transactions:
            trans.account_id = account_id
            self.storage.save_transaction(trans)
            count += 1
        return count

    def export_csv(self, file_path: str, account_id: str):
        """Export account transactions to CSV file."""
        transactions = self.get_transactions_for_account(account_id)
        CSVWriter.write_file(file_path, transactions)

    def import_ofx(self, file_path: str, account_id: str) -> int:
        """Import transactions from OFX file."""
        if not OFXImporter.is_available():
            raise ImportError("OFX support not available")

        transactions = OFXImporter.parse_file(file_path)
        count = 0
        for trans in transactions:
            trans.account_id = account_id
            self.storage.save_transaction(trans)
            count += 1
        return count

    # Payee operations
    def get_all_payees(self) -> List[str]:
        """Get all payees (both predefined and from transactions)."""
        return self.storage.get_all_payees()

    def add_payee(self, name: str):
        """Add a predefined payee."""
        self.storage.add_payee(name)

    def delete_payee(self, name: str):
        """Delete a predefined payee."""
        self.storage.delete_payee(name)

    def get_predefined_payees(self) -> List[str]:
        """Get only predefined payees."""
        return self.storage.get_predefined_payees()
