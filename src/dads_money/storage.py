"""SQLite storage layer for Dad's Money."""

import json
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

from .models import (
    Account,
    AccountType,
    SavingsAccountType,
    Category,
    Split,
    Transaction,
    TransactionStatus,
)


class Storage:
    """SQLite-based storage for financial data."""

    def __init__(self, db_path: Path):
        """Initialize storage with database path."""
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._ensure_database()

    def _ensure_database(self):
        """Create database and tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._migrate_schema()

    def _create_tables(self):
        """Create database schema."""
        cursor = self.conn.cursor()

        # Accounts table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                account_type TEXT NOT NULL,
                savings_subtype TEXT,
                opening_balance TEXT NOT NULL,
                current_balance TEXT NOT NULL,
                description TEXT,
                account_number TEXT,
                institution TEXT,
                created_date TEXT NOT NULL,
                closed INTEGER NOT NULL DEFAULT 0
            )
        """
        )

        # Categories table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                parent_id TEXT,
                is_income INTEGER NOT NULL DEFAULT 0,
                is_tax_related INTEGER NOT NULL DEFAULT 0,
                description TEXT,
                FOREIGN KEY (parent_id) REFERENCES categories(id)
            )
        """
        )

        # Transactions table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                date TEXT NOT NULL,
                payee TEXT,
                memo TEXT,
                amount TEXT NOT NULL,
                status TEXT,
                check_number TEXT,
                category_id TEXT,
                transfer_account_id TEXT,
                created_date TEXT NOT NULL,
                modified_date TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(id),
                FOREIGN KEY (category_id) REFERENCES categories(id),
                FOREIGN KEY (transfer_account_id) REFERENCES accounts(id)
            )
        """
        )

        # Splits table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS splits (
                id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL,
                category_id TEXT,
                transfer_account_id TEXT,
                amount TEXT NOT NULL,
                memo TEXT,
                FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id),
                FOREIGN KEY (transfer_account_id) REFERENCES accounts(id)
            )
        """
        )

        # Payees table for predefined payees
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS payees (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                created_date TEXT NOT NULL
            )
        """
        )

        # Indexes for performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_account ON transactions(account_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trans_date ON transactions(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_splits_trans ON splits(transaction_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_payees_name ON payees(name)")

        self.conn.commit()
        self._seed_default_categories()

    def _migrate_schema(self):
        """Migrate database schema to latest version."""
        cursor = self.conn.cursor()

        # Check if savings_subtype column exists in accounts table
        cursor.execute("PRAGMA table_info(accounts)")
        columns = [row[1] for row in cursor.fetchall()]

        if "savings_subtype" not in columns:
            # Add savings_subtype column
            cursor.execute("ALTER TABLE accounts ADD COLUMN savings_subtype TEXT")
            self.conn.commit()

    def _seed_default_categories(self):
        """Create default categories if none exist."""
        cursor = self.conn.cursor()
        count = cursor.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count > 0:
            return

        # Default categories similar to Microsoft Money
        default_categories = [
            Category(name="Income", is_income=True),
            Category(name="Salary", is_income=True),
            Category(name="Interest Income", is_income=True),
            Category(name="Dividend Income", is_income=True),
            Category(name="Auto", is_income=False),
            Category(name="Banking", is_income=False),
            Category(name="Bills", is_income=False),
            Category(name="Clothing", is_income=False),
            Category(name="Dining", is_income=False),
            Category(name="Entertainment", is_income=False),
            Category(name="Gifts", is_income=False),
            Category(name="Groceries", is_income=False),
            Category(name="Healthcare", is_income=False),
            Category(name="Home", is_income=False),
            Category(name="Insurance", is_income=False),
            Category(name="Personal Care", is_income=False),
            Category(name="Taxes", is_income=False, is_tax_related=True),
            Category(name="Transportation", is_income=False),
            Category(name="Utilities", is_income=False),
        ]

        for cat in default_categories:
            self.save_category(cat)

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    # Account operations
    def save_account(self, account: Account):
        """Save or update an account."""
        cursor = self.conn.cursor()

        # Handle savings_subtype
        savings_subtype_value = None
        if account.savings_subtype:
            savings_subtype_value = account.savings_subtype.value

        cursor.execute(
            """
            INSERT OR REPLACE INTO accounts
            (id, name, account_type, savings_subtype, opening_balance, current_balance, description,
             account_number, institution, created_date, closed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                account.id,
                account.name,
                account.account_type.value,
                savings_subtype_value,
                str(account.opening_balance),
                str(account.current_balance),
                account.description,
                account.account_number,
                account.institution,
                account.created_date.isoformat(),
                int(account.closed),
            ),
        )
        self.conn.commit()

    def get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        cursor = self.conn.cursor()
        row = cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if not row:
            return None
        return self._row_to_account(row)

    def get_all_accounts(self, include_closed: bool = False) -> List[Account]:
        """Get all accounts."""
        cursor = self.conn.cursor()
        query = "SELECT * FROM accounts"
        if not include_closed:
            query += " WHERE closed = 0"
        query += " ORDER BY name"
        rows = cursor.execute(query).fetchall()
        return [self._row_to_account(row) for row in rows]

    def delete_account(self, account_id: str):
        """Delete an account."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        self.conn.commit()

    def _row_to_account(self, row) -> Account:
        """Convert database row to Account object."""
        account_type_value = row["account_type"]
        if account_type_value == "Checking":
            account_type_value = AccountType.CHECKING.value

        # Handle savings_subtype
        savings_subtype = None
        if row["savings_subtype"]:
            try:
                savings_subtype = SavingsAccountType(row["savings_subtype"])
            except ValueError:
                # If the saved value is not valid, default to None
                savings_subtype = None

        return Account(
            id=row["id"],
            name=row["name"],
            account_type=AccountType(account_type_value),
            savings_subtype=savings_subtype,
            opening_balance=Decimal(row["opening_balance"]),
            current_balance=Decimal(row["current_balance"]),
            description=row["description"] or "",
            account_number=row["account_number"] or "",
            institution=row["institution"] or "",
            created_date=date.fromisoformat(row["created_date"]),
            closed=bool(row["closed"]),
        )

    # Category operations
    def save_category(self, category: Category):
        """Save or update a category."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO categories
            (id, name, parent_id, is_income, is_tax_related, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                category.id,
                category.name,
                category.parent_id,
                int(category.is_income),
                int(category.is_tax_related),
                category.description,
            ),
        )
        self.conn.commit()

    def get_category(self, category_id: str) -> Optional[Category]:
        """Get category by ID."""
        cursor = self.conn.cursor()
        row = cursor.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        if not row:
            return None
        return self._row_to_category(row)

    def get_all_categories(self) -> List[Category]:
        """Get all categories."""
        cursor = self.conn.cursor()
        rows = cursor.execute("SELECT * FROM categories ORDER BY name").fetchall()
        return [self._row_to_category(row) for row in rows]

    def delete_category(self, category_id: str):
        """Delete a category."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        self.conn.commit()

    def _row_to_category(self, row) -> Category:
        """Convert database row to Category object."""
        return Category(
            id=row["id"],
            name=row["name"],
            parent_id=row["parent_id"],
            is_income=bool(row["is_income"]),
            is_tax_related=bool(row["is_tax_related"]),
            description=row["description"] or "",
        )

    # Transaction operations
    def save_transaction(self, transaction: Transaction):
        """Save or update a transaction with splits."""
        cursor = self.conn.cursor()

        # Save transaction
        cursor.execute(
            """
            INSERT OR REPLACE INTO transactions
            (id, account_id, date, payee, memo, amount, status, check_number,
             category_id, transfer_account_id, created_date, modified_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                transaction.id,
                transaction.account_id,
                transaction.date.isoformat(),
                transaction.payee,
                transaction.memo,
                str(transaction.amount),
                transaction.status.value,
                transaction.check_number,
                transaction.category_id,
                transaction.transfer_account_id,
                transaction.created_date.isoformat(),
                transaction.modified_date.isoformat(),
            ),
        )

        # Delete old splits and insert new ones
        cursor.execute("DELETE FROM splits WHERE transaction_id = ?", (transaction.id,))
        for split in transaction.splits:
            cursor.execute(
                """
                INSERT INTO splits
                (id, transaction_id, category_id, transfer_account_id, amount, memo)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    split.id,
                    transaction.id,
                    split.category_id,
                    split.transfer_account_id,
                    str(split.amount),
                    split.memo,
                ),
            )

        self.conn.commit()
        self._update_account_balance(transaction.account_id)

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Get transaction by ID."""
        cursor = self.conn.cursor()
        row = cursor.execute(
            "SELECT * FROM transactions WHERE id = ?", (transaction_id,)
        ).fetchone()
        if not row:
            return None

        transaction = self._row_to_transaction(row)

        # Load splits
        split_rows = cursor.execute(
            "SELECT * FROM splits WHERE transaction_id = ?", (transaction_id,)
        ).fetchall()
        transaction.splits = [self._row_to_split(row) for row in split_rows]

        return transaction

    def get_transactions_for_account(self, account_id: str) -> List[Transaction]:
        """Get all transactions for an account."""
        cursor = self.conn.cursor()
        rows = cursor.execute(
            "SELECT * FROM transactions WHERE account_id = ? ORDER BY date DESC, created_date DESC",
            (account_id,),
        ).fetchall()

        transactions = []
        for row in rows:
            transaction = self._row_to_transaction(row)
            # Load splits
            split_rows = cursor.execute(
                "SELECT * FROM splits WHERE transaction_id = ?", (transaction.id,)
            ).fetchall()
            transaction.splits = [self._row_to_split(row) for row in split_rows]
            transactions.append(transaction)

        return transactions

    def delete_transaction(self, transaction_id: str, account_id: str):
        """Delete a transaction."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM splits WHERE transaction_id = ?", (transaction_id,))
        cursor.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))
        self.conn.commit()
        self._update_account_balance(account_id)

    def _row_to_transaction(self, row) -> Transaction:
        """Convert database row to Transaction object."""
        return Transaction(
            id=row["id"],
            account_id=row["account_id"],
            date=date.fromisoformat(row["date"]),
            payee=row["payee"] or "",
            memo=row["memo"] or "",
            amount=Decimal(row["amount"]),
            status=TransactionStatus(row["status"] or ""),
            check_number=row["check_number"] or "",
            category_id=row["category_id"],
            transfer_account_id=row["transfer_account_id"],
            created_date=datetime.fromisoformat(row["created_date"]),
            modified_date=datetime.fromisoformat(row["modified_date"]),
        )

    def _row_to_split(self, row) -> Split:
        """Convert database row to Split object."""
        return Split(
            id=row["id"],
            category_id=row["category_id"],
            transfer_account_id=row["transfer_account_id"],
            amount=Decimal(row["amount"]),
            memo=row["memo"] or "",
        )

    # Payee operations
    def get_all_payees(self) -> List[str]:
        """Get all payees (both predefined and from transactions)."""
        cursor = self.conn.cursor()

        # Get predefined payees
        predefined = cursor.execute("SELECT name FROM payees ORDER BY name").fetchall()
        payees = set(row["name"] for row in predefined)

        # Get unique payees from transactions
        transaction_payees = cursor.execute(
            "SELECT DISTINCT payee FROM transactions WHERE payee IS NOT NULL AND payee != '' ORDER BY payee"
        ).fetchall()
        payees.update(row["payee"] for row in transaction_payees)

        return sorted(list(payees))

    def add_payee(self, name: str):
        """Add a predefined payee."""
        from uuid import uuid4
        from datetime import datetime

        if not name or not name.strip():
            return

        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO payees (id, name, created_date)
                VALUES (?, ?, ?)
            """,
                (str(uuid4()), name.strip(), datetime.now().isoformat()),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            # Payee already exists
            pass

    def delete_payee(self, name: str):
        """Delete a predefined payee."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM payees WHERE name = ?", (name,))
        self.conn.commit()

    def get_predefined_payees(self) -> List[str]:
        """Get only predefined payees."""
        cursor = self.conn.cursor()
        rows = cursor.execute("SELECT name FROM payees ORDER BY name").fetchall()
        return [row["name"] for row in rows]

    def _update_account_balance(self, account_id: str):
        """Recalculate account balance from transactions."""
        cursor = self.conn.cursor()

        # Get opening balance
        account_row = cursor.execute(
            "SELECT opening_balance FROM accounts WHERE id = ?", (account_id,)
        ).fetchone()
        if not account_row:
            return

        opening_balance = Decimal(account_row["opening_balance"])

        # Sum all transactions
        result = cursor.execute(
            "SELECT SUM(CAST(amount AS REAL)) as total FROM transactions WHERE account_id = ?",
            (account_id,),
        ).fetchone()

        transaction_total = Decimal(str(result["total"] or 0))
        new_balance = opening_balance + transaction_total

        # Update account
        cursor.execute(
            "UPDATE accounts SET current_balance = ? WHERE id = ?", (str(new_balance), account_id)
        )
        self.conn.commit()
