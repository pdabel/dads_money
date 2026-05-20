"""Application services layer."""

from datetime import date as Date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import Config
from .io_csv import CSVParser, CSVWriter, InvestmentCSVParser, InvestmentCSVWriter
from .io_ofx import OFXImporter
from .io_qif import InvestmentQIFParser, QIFParser, QIFWriter
from .models import (
    Account,
    AccountType,
    Category,
    Holding,
    InvestmentTransaction,
    InvestmentTransactionType,
    PortfolioSummary,
    SavingsAccountType,
    Security,
    SecurityPrice,
    SecurityType,
    Transaction,
    TransactionStatus,
)
from .settings import get_settings
from .storage import Storage

try:
    import yfinance as yf

    _YFINANCE_AVAILABLE = True
except ImportError:
    _YFINANCE_AVAILABLE = False

# Investment transaction types where cash flows *into* the linked bank account
_BANK_INCOME_TYPES = frozenset(
    {
        InvestmentTransactionType.SELL,
        InvestmentTransactionType.DIV,
        InvestmentTransactionType.INT_INC,
        InvestmentTransactionType.MISC_INC,
        InvestmentTransactionType.RETURN_CAPITAL,
    }
)


class MoneyService:
    """Main application service coordinating storage and business logic."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the service."""
        if db_path is None:
            db_path = Config.get_database_path()
        self.storage = Storage(db_path)
        self._categories_cache: Optional[List[Category]] = None

    def close(self) -> None:
        """Close the service and underlying storage."""
        self.storage.close()

    # Account operations
    def create_account(
        self,
        name: str,
        account_type: Any,
        opening_balance: float = 0.0,
        savings_subtype: Any = None,
        owner: str = "",
    ) -> Account:
        """Create a new account."""

        balance = Decimal(str(opening_balance))
        account = Account(
            name=name,
            account_type=account_type,
            savings_subtype=savings_subtype,
            opening_balance=balance,
            current_balance=balance,
            owner=owner,
        )
        self.storage.save_account(account)
        return account

    def get_account(self, account_id: str) -> Optional[Account]:
        """Get account by ID."""
        return self.storage.get_account(account_id)

    def get_all_accounts(
        self, include_closed: bool = False, include_hidden: bool = False
    ) -> List[Account]:
        """Get all accounts."""
        return self.storage.get_all_accounts(include_closed, include_hidden)

    def update_account(self, account: Account) -> None:
        """Update an existing account."""
        self.storage.save_account(account)
        self.storage._update_account_balance(account.id)

    def delete_account(self, account_id: str) -> None:
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
        assert self._categories_cache is not None
        return self._categories_cache

    def get_categories_dict(self) -> Dict[str, Category]:
        """Get categories as a dictionary keyed by ID."""
        return {cat.id: cat for cat in self.get_all_categories()}

    def update_category(self, category: Category) -> None:
        """Update an existing category."""
        self.storage.save_category(category)
        self._categories_cache = None

    def delete_category(self, category_id: str) -> None:
        """Delete a category."""
        self.storage.delete_category(category_id)
        self._categories_cache = None

    # Transaction operations
    def create_transaction(
        self,
        account_id: str,
        date: Any,
        amount: float,
        payee: str = "",
        memo: str = "",
        check_number: str = "",
        status: Any = None,
        category_id: Optional[str] = None,
    ) -> Transaction:
        """Create a new transaction."""
        from .models import TransactionStatus

        transaction = Transaction(
            account_id=account_id,
            date=date,
            amount=Decimal(str(amount)),
            payee=payee,
            memo=memo,
            check_number=check_number,
            status=status if status is not None else TransactionStatus.UNCLEARED,
            category_id=category_id,
        )
        self.storage.save_transaction(transaction)
        return transaction

    def get_transaction(self, transaction_id: str) -> Optional[Transaction]:
        """Get transaction by ID."""
        return self.storage.get_transaction(transaction_id)

    def get_transactions_for_account(self, account_id: str) -> List[Transaction]:
        """Get all transactions for an account."""
        return self.storage.get_transactions_for_account(account_id)

    def update_transaction(self, transaction: Transaction) -> None:
        """Update an existing transaction."""
        transaction.modified_date = datetime.now()
        self.storage.save_transaction(transaction)

    def delete_transaction(self, transaction_id: str, account_id: str) -> None:
        """Delete a transaction."""
        self.storage.delete_transaction(transaction_id, account_id)

    # Transfer operations

    def create_transfer(
        self,
        from_account_id: str,
        to_account_id: str,
        transfer_date: Date,
        amount: float,
        payee: str = "Transfer",
        memo: str = "",
        status: TransactionStatus = TransactionStatus.UNCLEARED,
    ) -> Tuple[Transaction, Transaction]:
        """Create a linked pair of transfer transactions between two accounts.

        Args:
            from_account_id: Account to debit (money leaves).
            to_account_id: Account to credit (money arrives).
            transfer_date: Date of the transfer.
            amount: Positive value; source gets -amount, destination gets +amount.
            payee: Payee label shown on both sides.
            memo: Optional memo copied to both sides.
            status: Cleared/reconciled status for both transactions.

        Returns:
            Tuple of (source_transaction, destination_transaction).
        """
        decimal_amount = Decimal(str(amount))

        src_txn = Transaction(
            account_id=from_account_id,
            date=transfer_date,
            amount=-decimal_amount,
            payee=payee,
            memo=memo,
            status=status,
            transfer_account_id=to_account_id,
        )
        self.storage.save_transaction(src_txn)

        dst_txn = Transaction(
            account_id=to_account_id,
            date=transfer_date,
            amount=decimal_amount,
            payee=payee,
            memo=memo,
            status=status,
            transfer_account_id=from_account_id,
        )
        self.storage.save_transaction(dst_txn)

        return src_txn, dst_txn

    def find_linked_transfer_transaction(self, transaction: Transaction) -> Optional[Transaction]:
        """Return the counterpart transaction for a transfer, or None if not found.

        Args:
            transaction: One side of a transfer (must have transfer_account_id set).

        Returns:
            The matching transaction in the linked account, or None.
        """
        if not transaction.transfer_account_id:
            return None
        candidates = self.storage.get_transactions_for_account(transaction.transfer_account_id)
        for candidate in candidates:
            if (
                candidate.transfer_account_id == transaction.account_id
                and candidate.date == transaction.date
                and candidate.amount == -transaction.amount
                and candidate.payee == transaction.payee
            ):
                return candidate
        return None

    def delete_transfer(self, transaction_id: str, account_id: str) -> None:
        """Delete both sides of a transfer transaction.

        Args:
            transaction_id: ID of either side of the transfer to delete.
            account_id: Account the given transaction belongs to.
        """
        transaction = self.storage.get_transaction(transaction_id)
        if transaction and transaction.transfer_account_id:
            linked = self.find_linked_transfer_transaction(transaction)
            if linked:
                self.storage.delete_transaction(linked.id, transaction.transfer_account_id)
        self.storage.delete_transaction(transaction_id, account_id)

    # Import/Export operations
    def import_qif(self, file_path: str, account_id: str) -> int:
        """Import transactions from QIF file.

        Routes to investment-aware parsing when the target account is an
        investment account *or* when the file contains ``!Type:Invst`` data.
        """
        account = self.storage.get_account(account_id)
        is_investment = (
            account is not None and account.account_type == AccountType.INVESTMENT
        ) or InvestmentQIFParser.is_investment_qif(file_path)

        if is_investment:
            records = InvestmentQIFParser.parse_file(file_path)
            return self._save_investment_import_records(records, account_id)

        transactions = QIFParser.parse_file(file_path)
        count = 0
        for trans in transactions:
            trans.account_id = account_id
            if self.storage.transaction_exists(account_id, trans.date, trans.amount, trans.payee):
                continue
            self.storage.save_transaction(trans)
            count += 1
        return count

    def export_qif(self, file_path: str, account_id: str) -> int:
        """Export account transactions to QIF file.

        Returns the number of transactions written.
        """
        transactions = self.get_transactions_for_account(account_id)
        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        account_type_map = {
            "Current Account": "Bank",
            "Checking": "Bank",
            "Savings": "Bank",
            "Credit Card": "CCard",
            "Cash": "Cash",
        }
        qif_type = account_type_map.get(account.account_type.value, "Bank")
        QIFWriter.write_file(file_path, transactions, qif_type)
        return len(transactions)

    def import_csv(self, file_path: str, account_id: str) -> int:
        """Import transactions from CSV file.

        Routes to investment-aware parsing when the target account is an
        investment account *or* when the file has investment-style headers.
        """
        account = self.storage.get_account(account_id)
        is_investment = (
            account is not None and account.account_type == AccountType.INVESTMENT
        ) or InvestmentCSVParser.is_investment_csv(file_path)

        if is_investment:
            records = InvestmentCSVParser.parse_file(file_path)
            return self._save_investment_import_records(records, account_id)

        transactions = CSVParser.parse_file(file_path)
        count = 0
        for trans in transactions:
            trans.account_id = account_id
            if self.storage.transaction_exists(account_id, trans.date, trans.amount, trans.payee):
                continue
            self.storage.save_transaction(trans)
            count += 1
        return count

    def export_csv(self, file_path: str, account_id: str) -> int:
        """Export account transactions to CSV file.

        Investment accounts are written with investment-specific columns
        (Action, Security, Quantity, Price, Commission); all other account
        types use the standard transaction columns.

        Returns the number of transactions written.
        """
        account = self.get_account(account_id)
        if account and account.account_type == AccountType.INVESTMENT:
            inv_transactions = self.get_investment_transactions_for_account(account_id)
            securities = {s.id: s.name for s in self.storage.get_all_securities()}
            InvestmentCSVWriter.write_file(file_path, inv_transactions, securities)
            return len(inv_transactions)
        else:
            transactions = self.get_transactions_for_account(account_id)
            CSVWriter.write_file(file_path, transactions)
            return len(transactions)

    def import_ofx(self, file_path: str, account_id: str) -> int:
        """Import transactions from OFX file."""
        if not OFXImporter.is_available():
            raise ImportError("OFX support not available")

        transactions = OFXImporter.parse_file(file_path)
        count = 0
        for trans in transactions:
            trans.account_id = account_id
            if self.storage.transaction_exists(account_id, trans.date, trans.amount, trans.payee):
                continue
            self.storage.save_transaction(trans)
            count += 1
        return count

    def _save_investment_import_records(
        self,
        records: list,
        account_id: str,
    ) -> int:
        """Persist a list of ``InvestmentImportRecord`` objects.

        Securities are matched by name (case-insensitive) against existing
        records; new ones are auto-created with the name and no ticker so the
        user can enrich them later via Manage Securities.
        """
        from .io_qif import InvestmentImportRecord  # local import avoids circular ref at module top

        # Build a case-insensitive name → Security map once
        sec_by_name: dict = {s.name.lower(): s for s in self.storage.get_all_securities()}

        # Build a case-insensitive name → Account map for linked-transfer synthesis
        accts_by_name: dict = {
            a.name.lower(): a for a in self.storage.get_all_accounts(include_closed=True)
        }

        count = 0
        for rec in records:
            # Resolve or create security
            security_id: Optional[str] = None
            if rec.security_name:
                key = rec.security_name.lower()
                if key not in sec_by_name:
                    new_sec = Security(
                        name=rec.security_name,
                        ticker_symbol="",
                        security_type=SecurityType.STOCK,
                    )
                    self.storage.save_security(new_sec)
                    sec_by_name[key] = new_sec
                security_id = sec_by_name[key].id

            # X-variant actions (BuyX, SellX, DivX …) mean the cash was
            # transferred to/from another account, so this account has zero
            # cash impact.  For regular actions, recompute from qty/price when
            # available, falling back to the raw T-field amount.
            if rec.is_transfer:
                amount = Decimal("0")
            elif rec.quantity != Decimal("0") and rec.price != Decimal("0"):
                amount = _compute_cash_amount(
                    rec.transaction_type, rec.quantity, rec.price, rec.commission
                )
            else:
                amount = rec.amount

            # Persist the per-date price from the I field so the holdings
            # panel can compute market value without a manual price entry.
            if security_id and rec.price != Decimal("0"):
                self.add_security_price(security_id, rec.date, rec.price, source="import")

            if self.storage.investment_transaction_exists(
                account_id,
                rec.date,
                rec.transaction_type.value,
                security_id,
                rec.quantity,
                amount,
            ):
                continue

            txn = InvestmentTransaction(
                account_id=account_id,
                security_id=security_id,
                date=rec.date,
                transaction_type=rec.transaction_type,
                quantity=rec.quantity,
                price=rec.price,
                commission=rec.commission,
                amount=amount,
                memo=rec.memo,
                status=rec.status,
            )
            self.storage.save_investment_transaction(txn)
            count += 1

            # Synthesise the matching bank-side transaction when the QIF
            # recorded a linked account name (BuyX / SellX / DivX etc.)
            if rec.is_transfer and rec.linked_account_name:
                linked_acct = accts_by_name.get(rec.linked_account_name.lower())
                if linked_acct:
                    # Use the explicit $ amount if present, otherwise the T field
                    cash = (
                        rec.transfer_amount if rec.transfer_amount != Decimal("0") else rec.amount
                    )
                    # Sells/dividends etc. add cash; buys remove it
                    if rec.transaction_type in _BANK_INCOME_TYPES:
                        bank_amount = abs(cash)
                    else:
                        bank_amount = -abs(cash)
                    bank_payee = rec.security_name or linked_acct.name
                    if not self.storage.transaction_exists(
                        linked_acct.id, rec.date, bank_amount, bank_payee
                    ):
                        bank_txn = Transaction(
                            account_id=linked_acct.id,
                            date=rec.date,
                            payee=bank_payee,
                            amount=bank_amount,
                            memo=rec.memo,
                            status=rec.status,
                        )
                        self.storage.save_transaction(bank_txn)
                        count += 1

        return count

    # Payee operations
    def get_all_payees(self) -> List[str]:
        """Get all payees (both predefined and from transactions)."""
        return self.storage.get_all_payees()

    def add_payee(self, name: str) -> None:
        """Add a predefined payee."""
        self.storage.add_payee(name)

    def delete_payee(self, name: str) -> None:
        """Delete a predefined payee."""
        self.storage.delete_payee(name)

    def get_predefined_payees(self) -> List[str]:
        """Get only predefined payees."""
        return self.storage.get_predefined_payees()

    # -----------------------------------------------------------------------
    # Security operations
    # -----------------------------------------------------------------------

    def create_security(
        self,
        name: str,
        ticker_symbol: str = "",
        security_type: SecurityType = SecurityType.STOCK,
        notes: str = "",
        currency: str = "",
    ) -> Security:
        """Create and persist a new security."""
        security = Security(
            name=name,
            ticker_symbol=ticker_symbol,
            security_type=security_type,
            notes=notes,
            currency=currency,
        )
        self.storage.save_security(security)
        return security

    def get_security(self, security_id: str) -> Optional[Security]:
        return self.storage.get_security(security_id)

    def get_all_securities(self) -> List[Security]:
        return self.storage.get_all_securities()

    def update_security(self, security: Security) -> None:
        self.storage.save_security(security)

    def delete_security(self, security_id: str) -> None:
        self.storage.delete_security(security_id)

    # -----------------------------------------------------------------------
    # Security price operations
    # -----------------------------------------------------------------------

    def add_security_price(
        self,
        security_id: str,
        price_date: Date,
        price: Decimal,
        source: str = "manual",
    ) -> SecurityPrice:
        """Add (or update) a security price for a given date."""
        price_obj = SecurityPrice(
            security_id=security_id,
            date=price_date,
            price=price,
            source=source,
        )
        self.storage.save_security_price(price_obj)
        return price_obj

    def get_latest_price(self, security_id: str) -> Optional[SecurityPrice]:
        return self.storage.get_latest_price(security_id)

    def get_price_history(self, security_id: str) -> List[SecurityPrice]:
        return self.storage.get_price_history(security_id)

    # -----------------------------------------------------------------------
    # Investment transaction operations
    # -----------------------------------------------------------------------

    def create_investment_transaction(
        self,
        account_id: str,
        transaction_type: InvestmentTransactionType,
        txn_date: Date,
        security_id: Optional[str] = None,
        quantity: Decimal = Decimal("0"),
        price: Decimal = Decimal("0"),
        commission: Decimal = Decimal("0"),
        memo: str = "",
        status: TransactionStatus = TransactionStatus.UNCLEARED,
    ) -> InvestmentTransaction:
        """Create a new investment transaction, computing the cash amount."""
        amount = _compute_cash_amount(transaction_type, quantity, price, commission)
        txn = InvestmentTransaction(
            account_id=account_id,
            security_id=security_id,
            date=txn_date,
            transaction_type=transaction_type,
            quantity=quantity,
            price=price,
            commission=commission,
            amount=amount,
            memo=memo,
            status=status,
        )
        self.storage.save_investment_transaction(txn)
        return txn

    def get_investment_transaction(self, txn_id: str) -> Optional[InvestmentTransaction]:
        return self.storage.get_investment_transaction(txn_id)

    def get_investment_transactions_for_account(
        self, account_id: str
    ) -> List[InvestmentTransaction]:
        return self.storage.get_investment_transactions_for_account(account_id)

    def update_investment_transaction(
        self,
        txn: InvestmentTransaction,
        *,
        force_amount: Optional[Decimal] = None,
    ) -> None:
        """Recompute cash amount then persist.

        Pass *force_amount* to override the computed amount (e.g. when proceeds
        are transferred to another account and should not appear as cash here).
        """
        if force_amount is not None:
            txn.amount = force_amount
        else:
            txn.amount = _compute_cash_amount(
                txn.transaction_type, txn.quantity, txn.price, txn.commission
            )
        txn.modified_date = datetime.now()
        self.storage.save_investment_transaction(txn)

    def delete_investment_transaction(self, txn_id: str, account_id: str) -> None:
        self.storage.delete_investment_transaction(txn_id, account_id)

    # -----------------------------------------------------------------------
    # Portfolio / holdings computation
    # -----------------------------------------------------------------------

    def get_holdings_for_account(self, account_id: str) -> List[Holding]:
        """Return current holdings using average cost basis.

        Only securities with a non-zero share balance are returned.
        """
        transactions = self.storage.get_investment_transactions_for_account(account_id)
        # Must process in chronological order so BUY always precedes its SELL
        transactions = sorted(transactions, key=lambda t: (t.date, t.created_date))

        # Accumulate per-security: (total_shares, total_cost)
        shares: Dict[str, Decimal] = {}
        total_cost: Dict[str, Decimal] = {}

        for txn in transactions:
            if txn.security_id is None:
                continue
            sid = txn.security_id
            qty = txn.quantity

            if txn.transaction_type in (
                InvestmentTransactionType.BUY,
                InvestmentTransactionType.ADD,
                InvestmentTransactionType.REINV_DIV,
            ):
                shares[sid] = shares.get(sid, Decimal("0")) + qty
                cost = qty * txn.price + txn.commission
                total_cost[sid] = total_cost.get(sid, Decimal("0")) + cost

            elif txn.transaction_type == InvestmentTransactionType.SELL:
                held = shares.get(sid, Decimal("0"))
                avg = total_cost.get(sid, Decimal("0")) / held if held else Decimal("0")
                sell_qty = min(qty, held)
                shares[sid] = held - sell_qty
                total_cost[sid] = total_cost.get(sid, Decimal("0")) - avg * sell_qty

            elif txn.transaction_type == InvestmentTransactionType.REMOVE:
                shares[sid] = shares.get(sid, Decimal("0")) - qty

        holdings: List[Holding] = []
        for sid, sh in shares.items():
            if sh <= Decimal("0"):
                continue
            security = self.storage.get_security(sid)
            if security is None:
                continue
            tc = total_cost.get(sid, Decimal("0"))
            avg = tc / sh if sh else Decimal("0")

            latest_price_obj = self.storage.get_latest_price(sid)
            cp: Optional[Decimal]
            mv: Optional[Decimal]
            gl: Optional[Decimal]
            gl_pct: Optional[Decimal]
            if latest_price_obj is not None:
                cp = latest_price_obj.price
                mv = sh * cp
                gl = mv - tc
                gl_pct = (gl / tc * Decimal("100")) if tc else None
            else:
                cp = None
                mv = None
                gl = None
                gl_pct = None

            holdings.append(
                Holding(
                    security=security,
                    shares=sh,
                    avg_cost=avg,
                    total_cost=tc,
                    current_price=cp,
                    market_value=mv,
                    gain_loss=gl,
                    gain_loss_pct=gl_pct,
                )
            )

        holdings.sort(key=lambda h: h.security.name)
        return holdings

    def get_portfolio_summary(self, account_id: str) -> PortfolioSummary:
        """Return a summary of an investment account's portfolio."""
        account = self.storage.get_account(account_id)
        cash = account.current_balance if account else Decimal("0")

        holdings = self.get_holdings_for_account(account_id)

        hv: Optional[Decimal]
        total_val: Optional[Decimal]
        ugl: Optional[Decimal]
        if any(h.market_value is not None for h in holdings):
            hv = sum(
                (h.market_value for h in holdings if h.market_value is not None),
                Decimal("0"),
            )
            tc = sum((h.total_cost for h in holdings), Decimal("0"))
            total_val = cash + hv
            ugl = hv - tc
        else:
            hv = None
            total_val = None
            ugl = None
            tc = sum((h.total_cost for h in holdings), Decimal("0"))

        xirr_val = self.calculate_xirr(account_id)

        return PortfolioSummary(
            cash_balance=cash,
            total_cost=tc,
            holdings_value=hv,
            total_value=total_val,
            unrealized_gain_loss=ugl,
            roi_xirr=xirr_val,
        )

    # -----------------------------------------------------------------------
    # Live price fetching
    # -----------------------------------------------------------------------

    def _fetch_fx_rate(self, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """Fetch an FX spot rate from Yahoo Finance (e.g. USD → GBP via USDGBP=X).

        Returns None if the rate cannot be fetched.
        """
        if from_currency.upper() == to_currency.upper():
            return Decimal("1")
        ticker = f"{from_currency.upper()}{to_currency.upper()}=X"
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            raw = getattr(info, "last_price", None)
            if raw is None:
                return None
            return Decimal(str(raw))
        except Exception:
            return None

    def fetch_price_from_api(
        self,
        ticker: str,
        security_currency: str = "",
    ) -> Optional[Decimal]:
        """Fetch the latest price for a ticker via yfinance, converted to the
        app's base currency.

        Args:
            ticker: Yahoo Finance ticker symbol.
            security_currency: ISO code of the security's native currency
                (from ``Security.currency``). Empty means «same as app currency».

        Conversion rules applied in order:
        1. GBp / GBX (pence) → divide by 100 to get GBP pounds.
        2. If the reported currency differs from the app's base currency, fetch
           the FX rate ``{reported}{base}=X`` and multiply.

        Returns None on any failure.
        Raises ImportError if yfinance is not installed.
        """
        if not _YFINANCE_AVAILABLE:
            raise ImportError("yfinance is not installed. Run: pip install yfinance")
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            raw = getattr(info, "last_price", None)
            if raw is None:
                return None
            price = Decimal(str(raw))

            # --- Step 1: pence → pounds ---
            reported_currency = getattr(info, "currency", None) or ""
            if reported_currency.upper() in ("GBX", "GBP") and reported_currency != "GBP":
                # GBp (mixed case) = pence
                price = price / Decimal("100")
                reported_currency = "GBP"

            # --- Step 2: foreign currency → app base currency ---
            base_currency = get_settings().currency_code.upper()
            # Determine the effective currency of the price
            effective_currency = (
                reported_currency.upper()
                if reported_currency
                else (security_currency.upper() if security_currency else base_currency)
            )
            if effective_currency and effective_currency != base_currency:
                fx_rate = self._fetch_fx_rate(effective_currency, base_currency)
                if fx_rate is None:
                    # Can't convert — return None so the caller treats it as a failure
                    return None
                price = price * fx_rate

            return price
        except Exception:
            return None

    # -----------------------------------------------------------------------
    # XIRR / ROI
    # -----------------------------------------------------------------------

    def calculate_xirr(self, account_id: str) -> Optional[Decimal]:
        """Calculate annualised internal rate of return (XIRR) for an account.

        Cash flows are the investment transaction amounts (outflows negative,
        inflows positive). The terminal value is the current portfolio market
        value + cash balance (as a positive inflow on today's date).

        Returns None if there is insufficient data or no convergence.
        """
        transactions = self.storage.get_investment_transactions_for_account(account_id)
        if not transactions:
            return None

        cash_flows: List[Tuple[Date, Decimal]] = []
        for txn in transactions:
            if txn.amount != Decimal("0"):
                # Investment account perspective: outflows already negative
                cash_flows.append((txn.date, txn.amount))

        holdings = self.get_holdings_for_account(account_id)
        account = self.storage.get_account(account_id)
        cash_balance = account.current_balance if account else Decimal("0")

        if any(h.market_value is not None for h in holdings):
            holdings_total: Decimal = sum(
                (h.market_value for h in holdings if h.market_value is not None),
                Decimal("0"),
            )
            terminal = holdings_total + cash_balance
        else:
            # No prices — cannot compute meaningful XIRR
            return None

        today = Date.today()
        cash_flows.append((today, terminal))

        if len(cash_flows) < 2:
            return None

        result = _xirr(cash_flows)
        if result is None:
            return None
        return Decimal(str(round(result, 6)))

    # -----------------------------------------------------------------------
    # UK Tax report
    # -----------------------------------------------------------------------

    def generate_uk_tax_report(
        self,
        tax_year_start: int,
        account_ids: List[str],
        joint_account_ids: Optional[List[str]] = None,
    ) -> "UKTaxReport":
        """Generate a UK tax report for the specified tax year and accounts.

        The UK tax year runs from 6 April ``tax_year_start`` to
        5 April ``tax_year_start + 1`` (inclusive).

        Capital gains are computed using the Section 104 pool (average cost)
        method.  ISA accounts (Cash ISA and Stocks & Shares ISA) are
        flagged and excluded from taxable totals.

        If ``joint_account_ids`` is provided, amounts for those accounts are
        halved (50/50 split) to represent each co-owner's share.
        """
        from datetime import date as _Date
        from .models import (
            CapitalGainEvent,
            InvestmentIncomeItem,
            OtherIncomeItem,
            SavingsInterestItem,
            UKTaxReport,
        )

        year_start = _Date(tax_year_start, 4, 6)
        year_end = _Date(tax_year_start + 1, 4, 5)

        report = UKTaxReport(tax_year_start=tax_year_start)

        _joint_ids: set = set(joint_account_ids) if joint_account_ids else set()

        _isa_savings = {
            SavingsAccountType.CASH_ISA,
            SavingsAccountType.STOCKS_SHARES_ISA,
        }

        categories_dict = self.get_categories_dict()

        for account_id in account_ids:
            account = self.get_account(account_id)
            if account is None:
                continue

            is_inv = account.account_type == AccountType.INVESTMENT
            is_isa = account.savings_subtype in _isa_savings
            share = Decimal("0.5") if account_id in _joint_ids else Decimal("1")

            # ----------------------------------------------------------
            # Investment accounts — CGT + investment income
            # ----------------------------------------------------------
            if is_inv:
                # Use Section 104 pool (average cost) per security.
                # We must process *all* transactions chronologically to
                # build the correct pool before the tax year, then pick
                # up disposals within the year.
                all_inv_txns = self.storage.get_investment_transactions_for_account(account_id)
                all_inv_txns = sorted(all_inv_txns, key=lambda t: (t.date, t.created_date))

                # pool[security_id] = (total_shares, total_cost)
                pool: Dict[str, Tuple[Decimal, Decimal]] = {}

                for txn in all_inv_txns:
                    sid = txn.security_id
                    txn_type = txn.transaction_type

                    # ---- update the pool regardless of year ----
                    if txn_type in (
                        InvestmentTransactionType.BUY,
                        InvestmentTransactionType.ADD,
                    ):
                        if sid:
                            sh, tc = pool.get(sid, (Decimal("0"), Decimal("0")))
                            cost_added = txn.quantity * txn.price + txn.commission
                            pool[sid] = (sh + txn.quantity, tc + cost_added)

                    elif txn_type == InvestmentTransactionType.REINV_DIV:
                        if sid:
                            sh, tc = pool.get(sid, (Decimal("0"), Decimal("0")))
                            cost_added = txn.quantity * txn.price
                            pool[sid] = (sh + txn.quantity, tc + cost_added)

                    elif txn_type == InvestmentTransactionType.SELL:
                        if sid:
                            sh, tc = pool.get(sid, (Decimal("0"), Decimal("0")))
                            avg = tc / sh if sh else Decimal("0")
                            sell_qty = min(txn.quantity, sh)
                            cost_of_sale = avg * sell_qty
                            pool[sid] = (
                                sh - sell_qty,
                                tc - cost_of_sale,
                            )
                            # Only record the disposal if it falls in this tax year
                            if year_start <= txn.date <= year_end:
                                proceeds = (txn.quantity * txn.price - txn.commission) * share
                                cost_of_reported = cost_of_sale * share
                                gain = proceeds - cost_of_reported
                                security = self.get_security(sid)
                                sec_name = security.name if security else sid
                                report.capital_gains.append(
                                    CapitalGainEvent(
                                        date=txn.date,
                                        account_name=account.name,
                                        security_name=sec_name,
                                        quantity=txn.quantity,
                                        proceeds=proceeds,
                                        cost=cost_of_reported,
                                        gain=gain,
                                        is_isa=is_isa,
                                        share_pct=int(share * 100),
                                    )
                                )

                    elif txn_type == InvestmentTransactionType.REMOVE:
                        if sid:
                            sh, tc = pool.get(sid, (Decimal("0"), Decimal("0")))
                            avg = tc / sh if sh else Decimal("0")
                            rm_qty = min(txn.quantity, sh)
                            pool[sid] = (sh - rm_qty, tc - avg * rm_qty)

                    # ---- investment income in tax year ----
                    if not (year_start <= txn.date <= year_end):
                        continue

                    if txn_type in (
                        InvestmentTransactionType.DIV,
                        InvestmentTransactionType.REINV_DIV,
                        InvestmentTransactionType.INT_INC,
                        InvestmentTransactionType.MISC_INC,
                    ):
                        security = self.get_security(sid) if sid else None
                        sec_name = security.name if security else ""
                        income_amount = (
                            abs(txn.amount)
                            if txn.amount != Decimal("0")
                            else (txn.quantity * txn.price)
                        )
                        if income_amount > Decimal("0"):
                            report.investment_income.append(
                                InvestmentIncomeItem(
                                    date=txn.date,
                                    account_name=account.name,
                                    security_name=sec_name,
                                    income_type=txn_type.value,
                                    amount=income_amount * share,
                                    is_isa=is_isa,
                                    share_pct=int(share * 100),
                                )
                            )

            # ----------------------------------------------------------
            # Non-investment accounts — savings interest + other income
            # ----------------------------------------------------------
            else:
                # Build a set of known account IDs once for transfer detection.
                # (Lazy-initialised on first non-investment account.)
                if "_all_account_ids" not in dir():
                    _all_account_ids: set = {
                        a.id for a in self.storage.get_all_accounts(include_closed=True)
                    }

                txns = self.storage.get_transactions_for_account(account_id)
                for txn in txns:
                    if not (year_start <= txn.date <= year_end):
                        continue
                    if txn.amount <= Decimal("0"):
                        continue
                    # Skip inter-account transfers.
                    # A transaction is a transfer when:
                    #   (a) the top-level transfer_account_id points to a known account, OR
                    #   (b) any split's transfer_account_id points to a known account, OR
                    #   (c) QIF-imported transfer: memo contains "[Transfer: ..." pattern, OR
                    #   (d) payee is exactly "Transfer" (case-insensitive).
                    if txn.transfer_account_id in _all_account_ids:
                        continue
                    if any(s.transfer_account_id in _all_account_ids for s in txn.splits):
                        continue
                    if "[Transfer:" in (txn.memo or ""):
                        continue
                    if (txn.payee or "").strip().lower().startswith("transfer"):
                        continue

                    category = (
                        categories_dict.get(txn.category_id or "") if txn.category_id else None
                    )

                    # Categorise as savings interest when:
                    #   - the category name contains "interest", OR
                    #   - the payee name contains "interest", OR
                    #   - the account is a Savings account and the transaction
                    #     has no category (uncategorised credit).
                    cat_name = category.name.lower() if category else ""
                    payee_name = txn.payee.lower()
                    is_interest = (
                        "interest" in cat_name
                        or "interest" in payee_name
                        or (account.account_type == AccountType.SAVINGS and category is None)
                    )

                    if is_interest:
                        report.savings_interest.append(
                            SavingsInterestItem(
                                date=txn.date,
                                account_name=account.name,
                                payee=txn.payee,
                                amount=txn.amount * share,
                                is_isa=is_isa,
                                share_pct=int(share * 100),
                            )
                        )
                    elif category is not None and category.is_income:
                        report.other_income.append(
                            OtherIncomeItem(
                                date=txn.date,
                                account_name=account.name,
                                payee=txn.payee,
                                category_name=category.full_name(categories_dict),
                                amount=txn.amount * share,
                                share_pct=int(share * 100),
                            )
                        )

        # Sort each section chronologically
        report.capital_gains.sort(key=lambda e: e.date)
        report.investment_income.sort(key=lambda e: e.date)
        report.savings_interest.sort(key=lambda e: e.date)
        report.other_income.sort(key=lambda e: e.date)

        return report

    # -----------------------------------------------------------------------
    # Account Summary report
    # -----------------------------------------------------------------------

    def generate_account_summary(
        self,
        start_date: Date,
        end_date: Date,
        account_ids: List[str],
    ) -> "AccountSummaryReport":
        """Generate an account summary report for a date range.

        For each account the method computes:
        - Opening balance: the account's balance just *before* ``start_date``
          (opening_balance + sum of all transactions before start_date).
        - Credits / debits / category breakdown for transactions whose date
          falls in [start_date, end_date].
        - Closing balance: opening_balance + net_change in period.

        Investment accounts are included with their cash-equivalent balance
        (the account's ``current_balance`` field, maintained by the storage
        layer) so their cash position is visible alongside bank accounts.
        """
        from .models import (
            AccountSummaryEntry,
            AccountSummaryReport,
            CategorySummaryRow,
        )

        report = AccountSummaryReport(start_date=start_date, end_date=end_date)
        categories_dict = self.get_categories_dict()

        for account_id in account_ids:
            account = self.get_account(account_id)
            if account is None:
                continue

            if account.account_type == AccountType.INVESTMENT:
                # For investment accounts use investment transaction amounts
                all_txns_inv = self.storage.get_investment_transactions_for_account(account_id)
                pre_period_inv = sum(t.amount for t in all_txns_inv if t.date < start_date)
                opening = account.opening_balance + pre_period_inv

                in_period_inv = [t for t in all_txns_inv if start_date <= t.date <= end_date]
                credits = sum(t.amount for t in in_period_inv if t.amount > Decimal("0"))
                debits = sum(abs(t.amount) for t in in_period_inv if t.amount < Decimal("0"))

                # Category breakdown: group by transaction type
                cat_totals: Dict[str, Decimal] = {}
                for t in in_period_inv:
                    label = t.transaction_type.value
                    cat_totals[label] = cat_totals.get(label, Decimal("0")) + t.amount

                breakdown = [
                    CategorySummaryRow(category_name=k, amount=v)
                    for k, v in sorted(cat_totals.items())
                    if v != Decimal("0")
                ]

                report.entries.append(
                    AccountSummaryEntry(
                        account_name=account.name,
                        account_type=account.account_type.value,
                        opening_balance=opening,
                        closing_balance=opening + credits - debits,
                        total_credits=credits,
                        total_debits=debits,
                        category_breakdown=breakdown,
                        transaction_count=len(in_period_inv),
                    )
                )
            else:
                # Bank / savings / credit-card accounts
                all_txns = self.storage.get_transactions_for_account(account_id)
                pre_period = sum(t.amount for t in all_txns if t.date < start_date)
                opening = account.opening_balance + pre_period

                in_period = [t for t in all_txns if start_date <= t.date <= end_date]
                credits = sum(t.amount for t in in_period if t.amount > Decimal("0"))
                debits = sum(abs(t.amount) for t in in_period if t.amount < Decimal("0"))

                # Category breakdown
                cat_totals_b: Dict[str, Decimal] = {}
                for t in in_period:
                    if t.is_split():
                        for split in t.splits:
                            cat = categories_dict.get(split.category_id or "")
                            label = cat.full_name(categories_dict) if cat else "Uncategorised"
                            cat_totals_b[label] = (
                                cat_totals_b.get(label, Decimal("0")) + split.amount
                            )
                    else:
                        cat = categories_dict.get(t.category_id or "") if t.category_id else None
                        label = cat.full_name(categories_dict) if cat else "Uncategorised"
                        cat_totals_b[label] = cat_totals_b.get(label, Decimal("0")) + t.amount

                breakdown_b = [
                    CategorySummaryRow(category_name=k, amount=v)
                    for k, v in sorted(cat_totals_b.items())
                    if v != Decimal("0")
                ]

                report.entries.append(
                    AccountSummaryEntry(
                        account_name=account.name,
                        account_type=account.account_type.value,
                        opening_balance=opening,
                        closing_balance=opening + credits - debits,
                        total_credits=credits,
                        total_debits=debits,
                        category_breakdown=breakdown_b,
                        transaction_count=len(in_period),
                    )
                )

        return report


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

# Types that involve share quantity changes (used for validation elsewhere)
_QUANTITY_TYPES = frozenset(
    [
        InvestmentTransactionType.BUY,
        InvestmentTransactionType.SELL,
        InvestmentTransactionType.ADD,
        InvestmentTransactionType.REMOVE,
        InvestmentTransactionType.REINV_DIV,
    ]
)


def _compute_cash_amount(
    txn_type: InvestmentTransactionType,
    quantity: Decimal,
    price: Decimal,
    commission: Decimal,
) -> Decimal:
    """Compute the cash impact of an investment transaction."""
    if txn_type == InvestmentTransactionType.BUY:
        return -(quantity * price + commission)
    elif txn_type == InvestmentTransactionType.SELL:
        return quantity * price - commission
    elif txn_type == InvestmentTransactionType.MISC_EXP:
        # Use price as the cash amount when qty == 0 (symmetric with MISC_INC)
        if quantity == Decimal("0"):
            return -abs(price)
        return -(quantity * price + commission)
    elif txn_type in (
        InvestmentTransactionType.DIV,
        InvestmentTransactionType.INT_INC,
        InvestmentTransactionType.MISC_INC,
        InvestmentTransactionType.RETURN_CAPITAL,
    ):
        # For income types, `price` is used as the cash amount when qty == 0
        if quantity == Decimal("0"):
            return price
        return quantity * price
    else:
        # ADD, REMOVE, REINV_DIV — no direct cash impact
        return Decimal("0")


def _xirr(cash_flows: List[Tuple[Date, Decimal]]) -> Optional[float]:
    """Newton-Raphson XIRR.  Returns the rate or None if not convergent."""
    if len(cash_flows) < 2:
        return None

    base_date = cash_flows[0][0]
    amounts = [float(cf[1]) for cf in cash_flows]
    years = [(cf[0] - base_date).days / 365.0 for cf in cash_flows]

    if all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts):
        return None  # No sign change — no valid IRR

    rate = 0.1  # initial guess
    for _ in range(200):
        npv = sum(a / (1 + rate) ** t for a, t in zip(amounts, years))
        d_npv = sum(-t * a / (1 + rate) ** (t + 1) for a, t in zip(amounts, years))
        if d_npv == 0:
            return None
        new_rate = rate - npv / d_npv
        if abs(new_rate - rate) < 1e-7:
            return float(new_rate)
        rate = new_rate
        if rate <= -1:
            rate = -0.9  # guard against degenerate move

    return None  # did not converge
