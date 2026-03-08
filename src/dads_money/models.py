"""Core data models for Dad's Money application."""

from dataclasses import dataclass, field
from datetime import date as Date, datetime as DateTime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict
from uuid import uuid4


class AccountType(Enum):
    """Account types supported by Microsoft Money."""

    CHECKING = "Current Account"
    SAVINGS = "Savings"
    CREDIT_CARD = "Credit Card"
    CASH = "Cash"
    INVESTMENT = "Investment"
    ASSET = "Asset"
    LIABILITY = "Liability"


class SavingsAccountType(Enum):
    """Types of savings accounts."""

    STANDARD = "Standard Savings"
    HIGH_INTEREST = "High Interest Savings"
    CASH_ISA = "Cash ISA"
    STOCKS_SHARES_ISA = "Stocks and Shares ISA"


class TransactionStatus(Enum):
    """Transaction reconciliation status."""

    CLEARED = "c"  # Cleared
    RECONCILED = "R"  # Reconciled
    UNCLEARED = ""  # Not cleared


@dataclass
class Category:
    """Expense/income category."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    parent_id: Optional[str] = None
    is_income: bool = False
    is_tax_related: bool = False
    description: str = ""

    def full_name(self, categories_dict: Optional[Dict[str, "Category"]] = None) -> str:
        """Get full category name including parent (e.g., 'Auto:Gas')."""
        if not self.parent_id or not categories_dict:
            return self.name
        parent = categories_dict.get(self.parent_id)
        if parent:
            return f"{parent.name}:{self.name}"
        return self.name


@dataclass
class Account:
    """Financial account."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    account_type: AccountType = AccountType.CHECKING
    savings_subtype: Optional[SavingsAccountType] = None
    opening_balance: Decimal = Decimal("0.00")
    current_balance: Decimal = Decimal("0.00")
    description: str = ""
    account_number: str = ""
    institution: str = ""
    created_date: Date = field(default_factory=Date.today)
    closed: bool = False

    def __post_init__(self) -> None:
        """Ensure balance is Decimal."""
        if not isinstance(self.opening_balance, Decimal):
            self.opening_balance = Decimal(str(self.opening_balance))
        if not isinstance(self.current_balance, Decimal):
            self.current_balance = Decimal(str(self.current_balance))


@dataclass
class Split:
    """Transaction split line item."""

    id: str = field(default_factory=lambda: str(uuid4()))
    category_id: Optional[str] = None
    transfer_account_id: Optional[str] = None  # For transfers between accounts
    amount: Decimal = Decimal("0.00")
    memo: str = ""

    def __post_init__(self) -> None:
        """Ensure amount is Decimal."""
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))


@dataclass
class Transaction:
    """Financial transaction."""

    id: str = field(default_factory=lambda: str(uuid4()))
    account_id: str = ""
    date: Date = field(default_factory=Date.today)
    payee: str = ""
    memo: str = ""
    amount: Decimal = Decimal("0.00")
    status: TransactionStatus = TransactionStatus.UNCLEARED
    check_number: str = ""

    # Category or splits
    category_id: Optional[str] = None
    transfer_account_id: Optional[str] = None
    splits: List[Split] = field(default_factory=list)

    created_date: DateTime = field(default_factory=DateTime.now)
    modified_date: DateTime = field(default_factory=DateTime.now)

    def __post_init__(self) -> None:
        """Ensure amount is Decimal."""
        if not isinstance(self.amount, Decimal):
            self.amount = Decimal(str(self.amount))

    def is_split(self) -> bool:
        """Check if transaction has splits."""
        return len(self.splits) > 0

    def validate_splits(self) -> bool:
        """Validate that split amounts sum to transaction amount."""
        if not self.is_split():
            return True
        split_total = sum(s.amount for s in self.splits)
        return split_total == self.amount
