"""Core data models for Dad's Money application."""

from dataclasses import dataclass, field
from datetime import date as Date, datetime as DateTime
from decimal import Decimal
from enum import Enum
from typing import Optional, List, Dict
from uuid import uuid4


# ---------------------------------------------------------------------------
# Investment enums
# ---------------------------------------------------------------------------


class SecurityType(Enum):
    """Types of investment securities."""

    STOCK = "Stock"
    MUTUAL_FUND = "Mutual Fund"
    BOND = "Bond"
    ETF = "ETF"
    OTHER = "Other"


class InvestmentTransactionType(Enum):
    """Investment transaction types matching MS Money 3.0 nomenclature."""

    BUY = "Buy"
    SELL = "Sell"
    DIV = "Dividend"
    REINV_DIV = "Reinvested Dividend"
    ADD = "Add Shares"
    REMOVE = "Remove Shares"
    MISC_INC = "Misc Income"
    MISC_EXP = "Misc Expense"
    RETURN_CAPITAL = "Return of Capital"
    INT_INC = "Interest Income"


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
    hidden: bool = False
    owner: str = ""  # Free text, e.g. "Alice", "Bob", "Joint". Empty = unassigned.

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


# ---------------------------------------------------------------------------
# Investment data models
# ---------------------------------------------------------------------------


@dataclass
class Security:
    """An investable security (stock, fund, bond, ETF, etc.)."""

    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    ticker_symbol: str = ""
    security_type: SecurityType = SecurityType.STOCK
    notes: str = ""
    currency: str = (
        ""  # ISO code of the security's native currency, e.g. "USD". Empty = same as app currency.
    )


@dataclass
class SecurityPrice:
    """A price record for a security on a given date."""

    id: str = field(default_factory=lambda: str(uuid4()))
    security_id: str = ""
    date: Date = field(default_factory=Date.today)
    price: Decimal = Decimal("0.00")
    source: str = "manual"  # 'manual' or 'api'

    def __post_init__(self) -> None:
        if not isinstance(self.price, Decimal):
            self.price = Decimal(str(self.price))


@dataclass
class InvestmentTransaction:
    """A transaction within an investment account.

    ``amount`` is the cash impact on the account:
    - BUY / MISC_EXP  → negative (cash leaves account)
    - SELL / DIV / INT_INC / MISC_INC / RETURN_CAPITAL → positive
    - ADD / REMOVE / REINV_DIV → zero (no cash movement)
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    account_id: str = ""
    security_id: Optional[str] = None  # None for pure-cash entries
    date: Date = field(default_factory=Date.today)
    transaction_type: InvestmentTransactionType = InvestmentTransactionType.BUY
    quantity: Decimal = Decimal("0")
    price: Decimal = Decimal("0.00")
    commission: Decimal = Decimal("0.00")
    amount: Decimal = Decimal("0.00")  # cash impact (computed or overridden)
    memo: str = ""
    status: TransactionStatus = TransactionStatus.UNCLEARED
    created_date: DateTime = field(default_factory=DateTime.now)
    modified_date: DateTime = field(default_factory=DateTime.now)

    def __post_init__(self) -> None:
        for attr in ("quantity", "price", "commission", "amount"):
            val = getattr(self, attr)
            if not isinstance(val, Decimal):
                setattr(self, attr, Decimal(str(val)))


@dataclass
class Holding:
    """Computed holding for a security within an investment account."""

    security: Security
    shares: Decimal
    avg_cost: Decimal  # per share
    total_cost: Decimal
    current_price: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    gain_loss: Optional[Decimal] = None
    gain_loss_pct: Optional[Decimal] = None


@dataclass
class PortfolioSummary:
    """Computed summary for an investment account."""

    cash_balance: Decimal
    total_cost: Decimal
    holdings_value: Optional[Decimal] = None  # None when no prices available
    total_value: Optional[Decimal] = None
    unrealized_gain_loss: Optional[Decimal] = None
    roi_xirr: Optional[Decimal] = None  # annualised rate, e.g. Decimal("0.0823") = 8.23%


# ---------------------------------------------------------------------------
# UK Tax report models
# ---------------------------------------------------------------------------


@dataclass
class CapitalGainEvent:
    """A single disposal event for UK Capital Gains Tax purposes."""

    date: Date
    account_name: str
    security_name: str
    quantity: Decimal
    proceeds: Decimal  # quantity × sale price − commission (already scaled by share)
    cost: Decimal  # average cost of shares disposed (already scaled by share)
    gain: Decimal  # proceeds − cost (may be negative = loss)
    is_isa: bool = False  # ISA disposals are CGT-exempt
    share_pct: int = 100  # 100 for sole-owner, 50 for joint (50/50 split)


@dataclass
class InvestmentIncomeItem:
    """A single dividend, interest or misc-income item from an investment account."""

    date: Date
    account_name: str
    security_name: str  # empty for pure-cash items (INT_INC with no security)
    income_type: str  # e.g. "Dividend", "Reinvested Dividend", "Interest Income"
    amount: Decimal
    is_isa: bool = False  # ISA income is tax-free
    share_pct: int = 100  # 100 for sole-owner, 50 for joint (50/50 split)


@dataclass
class SavingsInterestItem:
    """Interest received in a bank/savings account transaction."""

    date: Date
    account_name: str
    payee: str
    amount: Decimal
    is_isa: bool = False  # Cash ISA interest is tax-free
    share_pct: int = 100  # 100 for sole-owner, 50 for joint (50/50 split)


@dataclass
class OtherIncomeItem:
    """A taxable income transaction from a non-investment account."""

    date: Date
    account_name: str
    payee: str
    category_name: str
    amount: Decimal
    share_pct: int = 100  # 100 for sole-owner, 50 for joint (50/50 split)


@dataclass
class UKTaxReport:
    """Aggregated UK tax report for one tax year.

    The UK tax year runs from 6 April to 5 April the following year.
    ``tax_year_start`` is e.g. 2024 for the 2024/25 tax year.
    """

    tax_year_start: int
    capital_gains: List[CapitalGainEvent] = field(default_factory=list)
    investment_income: List[InvestmentIncomeItem] = field(default_factory=list)
    savings_interest: List[SavingsInterestItem] = field(default_factory=list)
    other_income: List[OtherIncomeItem] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience totals
    # ------------------------------------------------------------------

    @property
    def tax_year_label(self) -> str:
        return f"{self.tax_year_start}/{str(self.tax_year_start + 1)[-2:]}"

    @property
    def total_gains(self) -> Decimal:
        return sum(
            (e.gain for e in self.capital_gains if not e.is_isa and e.gain > 0),
            Decimal("0"),
        )

    @property
    def total_losses(self) -> Decimal:
        return sum(
            (abs(e.gain) for e in self.capital_gains if not e.is_isa and e.gain < 0),
            Decimal("0"),
        )

    @property
    def net_capital_gain(self) -> Decimal:
        return self.total_gains - self.total_losses

    @property
    def total_dividends(self) -> Decimal:
        return sum(
            (
                i.amount
                for i in self.investment_income
                if not i.is_isa and i.income_type in ("Dividend", "Reinvested Dividend")
            ),
            Decimal("0"),
        )

    @property
    def total_investment_interest(self) -> Decimal:
        return sum(
            (
                i.amount
                for i in self.investment_income
                if not i.is_isa and i.income_type not in ("Dividend", "Reinvested Dividend")
            ),
            Decimal("0"),
        )

    @property
    def total_savings_interest(self) -> Decimal:
        return sum(
            (i.amount for i in self.savings_interest if not i.is_isa),
            Decimal("0"),
        )

    @property
    def total_interest(self) -> Decimal:
        return self.total_investment_interest + self.total_savings_interest

    @property
    def total_other_income(self) -> Decimal:
        return sum((i.amount for i in self.other_income), Decimal("0"))


# ---------------------------------------------------------------------------
# Account Summary report models
# ---------------------------------------------------------------------------


@dataclass
class CategorySummaryRow:
    """A single category line in an account summary report."""

    category_name: str
    amount: Decimal  # positive = income/credit, negative = expense/debit


@dataclass
class AccountSummaryEntry:
    """Summary figures for a single account over a date range."""

    account_name: str
    account_type: str
    opening_balance: Decimal
    closing_balance: Decimal
    total_credits: Decimal  # sum of positive transactions in period
    total_debits: Decimal  # sum of absolute values of negative transactions in period
    category_breakdown: List[CategorySummaryRow]
    transaction_count: int

    @property
    def net_change(self) -> Decimal:
        return self.total_credits - self.total_debits


@dataclass
class AccountSummaryReport:
    """Aggregated account summary over a date range or tax year."""

    start_date: Date
    end_date: Date
    entries: List[AccountSummaryEntry] = field(default_factory=list)

    @property
    def period_label(self) -> str:
        return f"{self.start_date.strftime('%d %b %Y')} – {self.end_date.strftime('%d %b %Y')}"

    @property
    def total_credits(self) -> Decimal:
        return sum((e.total_credits for e in self.entries), Decimal("0"))

    @property
    def total_debits(self) -> Decimal:
        return sum((e.total_debits for e in self.entries), Decimal("0"))

    @property
    def net_change(self) -> Decimal:
        return self.total_credits - self.total_debits
