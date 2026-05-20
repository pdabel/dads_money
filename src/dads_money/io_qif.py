"""QIF (Quicken Interchange Format) import/export."""

from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from io import StringIO
from typing import Dict, List, Optional, TextIO

from .models import (
    InvestmentTransactionType,
    Transaction,
    TransactionStatus,
)


# ---------------------------------------------------------------------------
# Shared internal record produced by investment parsers
# ---------------------------------------------------------------------------


@dataclass
class InvestmentImportRecord:
    """Intermediate representation of one imported investment transaction.

    Security look-up / creation is deferred to the service layer.
    """

    date: date
    transaction_type: InvestmentTransactionType
    security_name: str  # raw name from file; "" for cash-only entries
    quantity: Decimal
    price: Decimal
    commission: Decimal
    amount: Decimal  # raw T/total field; service recomputes if qty+price known
    memo: str
    status: TransactionStatus
    is_transfer: bool = False  # True for BuyX/SellX/DivX etc. — no cash impact on this account
    linked_account_name: str = ""  # From L[Account Name] field
    transfer_amount: Decimal = Decimal("0")  # From $ field (cash moved in linked account)


# ---------------------------------------------------------------------------
# QIF action → InvestmentTransactionType mapping
# ---------------------------------------------------------------------------

_QIF_ACTION_MAP = {
    "buy": InvestmentTransactionType.BUY,
    "buyx": InvestmentTransactionType.BUY,
    "sell": InvestmentTransactionType.SELL,
    "sellx": InvestmentTransactionType.SELL,
    "div": InvestmentTransactionType.DIV,
    "divx": InvestmentTransactionType.DIV,
    "reinvdiv": InvestmentTransactionType.REINV_DIV,
    "shrsin": InvestmentTransactionType.ADD,
    "shrsout": InvestmentTransactionType.REMOVE,
    "miscinc": InvestmentTransactionType.MISC_INC,
    "miscincx": InvestmentTransactionType.MISC_INC,
    "miscexp": InvestmentTransactionType.MISC_EXP,
    "miscexpx": InvestmentTransactionType.MISC_EXP,
    "cglong": InvestmentTransactionType.MISC_INC,
    "cglongx": InvestmentTransactionType.MISC_INC,
    "cgshort": InvestmentTransactionType.MISC_INC,
    "cgshortx": InvestmentTransactionType.MISC_INC,
    "intinc": InvestmentTransactionType.INT_INC,
    "intincx": InvestmentTransactionType.INT_INC,
    "rtrncap": InvestmentTransactionType.RETURN_CAPITAL,
    "rtrncapx": InvestmentTransactionType.RETURN_CAPITAL,
}

# X-suffix actions mean proceeds/cost are transferred to/from another account,
# so the cash impact on *this* investment account is zero.
_QIF_TRANSFER_ACTIONS = frozenset(
    {
        "buyx",
        "sellx",
        "divx",
        "miscincx",
        "miscexpx",
        "intincx",
        "rtrncapx",
        "cglongx",
        "cgshortx",
    }
)


def _map_qif_action(action: str) -> InvestmentTransactionType:
    return _QIF_ACTION_MAP.get(action.lower(), InvestmentTransactionType.BUY)


class QIFParser:
    """Parse QIF format files."""

    @staticmethod
    def parse_file(
        file_path: str, account_name_to_id: Optional[Dict[str, str]] = None
    ) -> List[Transaction]:
        """Parse QIF file and return list of transactions.

        Args:
            file_path: Path to the QIF file.
            account_name_to_id: Optional mapping of account name → account ID.
                When provided, ``L[AccountName]`` fields are resolved to
                ``transfer_account_id`` instead of being appended to the memo.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            return QIFParser.parse(f, account_name_to_id)

    @staticmethod
    def parse(
        file: TextIO, account_name_to_id: Optional[Dict[str, str]] = None
    ) -> List[Transaction]:
        """Parse QIF format from file object.

        Args:
            file: Readable text stream.
            account_name_to_id: Optional mapping of account name → account ID.
                When provided, ``L[AccountName]`` fields are resolved to
                ``transfer_account_id`` instead of being appended to the memo.
        """
        transactions = []
        current_transaction = None

        for line in file:
            line = line.strip()
            if not line:
                continue

            if line == "!Type:Bank" or line == "!Type:Cash" or line == "!Type:CCard":
                continue

            if line == "^":
                if current_transaction:
                    transactions.append(current_transaction)
                    current_transaction = None
                continue

            if not line or len(line) < 2:
                continue

            field_type = line[0]
            field_value = line[1:].strip()

            if field_type == "D":  # Date
                if current_transaction is None:
                    current_transaction = Transaction()
                current_transaction.date = QIFParser._parse_date(field_value)

            elif field_type == "T":  # Amount
                if current_transaction is None:
                    current_transaction = Transaction()
                amount_str = field_value.replace(",", "")
                current_transaction.amount = Decimal(amount_str)

            elif field_type == "P":  # Payee
                if current_transaction is None:
                    current_transaction = Transaction()
                current_transaction.payee = field_value

            elif field_type == "M":  # Memo
                if current_transaction is None:
                    current_transaction = Transaction()
                current_transaction.memo = field_value

            elif field_type == "N":  # Check number
                if current_transaction is None:
                    current_transaction = Transaction()
                current_transaction.check_number = field_value

            elif field_type == "C":  # Cleared status
                if current_transaction is None:
                    current_transaction = Transaction()
                if field_value.upper() == "X" or field_value.upper() == "R":
                    current_transaction.status = TransactionStatus.RECONCILED
                elif field_value.upper() == "C" or field_value == "*":
                    current_transaction.status = TransactionStatus.CLEARED
                else:
                    current_transaction.status = TransactionStatus.UNCLEARED

            elif field_type == "L":  # Category or transfer
                if current_transaction is None:
                    current_transaction = Transaction()
                if field_value.startswith("[") and field_value.endswith("]"):
                    account_name = field_value[1:-1]
                    if account_name_to_id:
                        resolved_id = account_name_to_id.get(account_name)
                        if resolved_id:
                            current_transaction.transfer_account_id = resolved_id

        # Don't forget last transaction if file doesn't end with ^
        if current_transaction:
            transactions.append(current_transaction)

        return transactions

    @staticmethod
    def _parse_date(date_str: str) -> date:
        """Parse QIF date format."""
        # QIF supports multiple date formats: MM/DD/YYYY, MM/DD/YY, MM-DD-YYYY, etc.
        date_str = date_str.replace("'", "")  # Remove apostrophes

        for fmt in ["%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y", "%d/%m/%Y", "%d/%m/%y"]:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        # Default to today if we can't parse
        return datetime.now().date()


class QIFWriter:
    """Write transactions to QIF format."""

    @staticmethod
    def write_file(
        file_path: str,
        transactions: List[Transaction],
        account_type: str = "Bank",
        account_id_to_name: Optional[Dict[str, str]] = None,
    ) -> None:
        """Write transactions to QIF file.

        Args:
            file_path: Destination file path.
            transactions: Transactions to write.
            account_type: QIF account type header (Bank, CCard, Cash, etc.).
            account_id_to_name: Optional mapping of account ID → account name used
                to emit ``L[AccountName]`` fields for transfer transactions.
        """
        with open(file_path, "w", encoding="utf-8") as f:
            QIFWriter.write(f, transactions, account_type, account_id_to_name)

    @staticmethod
    def write(
        file: TextIO,
        transactions: List[Transaction],
        account_type: str = "Bank",
        account_id_to_name: Optional[Dict[str, str]] = None,
    ) -> None:
        """Write transactions to QIF format.

        Args:
            file: Writable text stream.
            transactions: Transactions to write.
            account_type: QIF account type header (Bank, CCard, Cash, etc.).
            account_id_to_name: Optional mapping of account ID → account name used
                to emit ``L[AccountName]`` fields for transfer transactions.
        """
        file.write(f"!Type:{account_type}\n")

        for trans in transactions:
            # Date
            file.write(f"D{trans.date.strftime('%m/%d/%Y')}\n")

            # Amount
            file.write(f"T{trans.amount}\n")

            # Payee
            if trans.payee:
                file.write(f"P{trans.payee}\n")

            # Memo
            if trans.memo:
                file.write(f"M{trans.memo}\n")

            # Check number
            if trans.check_number:
                file.write(f"N{trans.check_number}\n")

            # Cleared status
            if trans.status == TransactionStatus.RECONCILED:
                file.write("CR\n")
            elif trans.status == TransactionStatus.CLEARED:
                file.write("CC\n")
            else:
                file.write("C\n")

            # Transfer account link
            if trans.transfer_account_id and account_id_to_name:
                linked_name = account_id_to_name.get(trans.transfer_account_id)
                if linked_name:
                    file.write(f"L[{linked_name}]\n")

            # End of transaction
            file.write("^\n")


class InvestmentQIFParser:
    """Parse QIF files that contain investment (``!Type:Invst``) records."""

    @staticmethod
    def parse_file(file_path: str) -> List[InvestmentImportRecord]:
        with open(file_path, "r", encoding="utf-8") as f:
            return InvestmentQIFParser.parse(f)

    @staticmethod
    def is_investment_qif(file_path: str) -> bool:
        """Return True if the file contains a ``!Type:Invst`` header."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.upper() == "!TYPE:INVST":
                        return True
                    # Stop scanning after the first non-blank, non-Option line
                    if line and not line.startswith("!"):
                        return False
        except OSError:
            pass
        return False

    @staticmethod
    def parse(file: TextIO) -> List[InvestmentImportRecord]:
        records: List[InvestmentImportRecord] = []
        in_invst = False

        # Per-record accumulators
        rec_date: date = datetime.now().date()
        rec_type: InvestmentTransactionType = InvestmentTransactionType.BUY
        rec_security: str = ""
        rec_quantity: Decimal = Decimal("0")
        rec_price: Decimal = Decimal("0")
        rec_commission: Decimal = Decimal("0")
        rec_amount: Decimal = Decimal("0")
        rec_memo: str = ""
        rec_status: TransactionStatus = TransactionStatus.UNCLEARED
        rec_is_transfer: bool = False
        rec_linked_account: str = ""
        rec_transfer_amount: Decimal = Decimal("0")
        rec_started: bool = False

        def _flush() -> None:
            if rec_started:
                records.append(
                    InvestmentImportRecord(
                        date=rec_date,
                        transaction_type=rec_type,
                        security_name=rec_security,
                        quantity=rec_quantity,
                        price=rec_price,
                        commission=rec_commission,
                        amount=rec_amount,
                        memo=rec_memo,
                        status=rec_status,
                        is_transfer=rec_is_transfer,
                        linked_account_name=rec_linked_account,
                        transfer_amount=rec_transfer_amount,
                    )
                )

        def _reset() -> tuple:
            return (
                datetime.now().date(),
                InvestmentTransactionType.BUY,
                "",
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                "",
                TransactionStatus.UNCLEARED,
                False,  # is_transfer
                "",  # linked_account_name
                Decimal("0"),  # transfer_amount
                False,  # started
            )

        for raw_line in file:
            line = raw_line.strip()
            if not line:
                continue

            # Header lines
            if line.startswith("!"):
                if line.upper() == "!TYPE:INVST":
                    in_invst = True
                else:
                    in_invst = False
                continue

            if not in_invst:
                continue

            if line == "^":
                _flush()
                (
                    rec_date,
                    rec_type,
                    rec_security,
                    rec_quantity,
                    rec_price,
                    rec_commission,
                    rec_amount,
                    rec_memo,
                    rec_status,
                    rec_is_transfer,
                    rec_linked_account,
                    rec_transfer_amount,
                    rec_started,
                ) = _reset()
                continue

            if len(line) < 2:
                continue

            field = line[0]
            value = line[1:].strip()

            rec_started = True

            if field == "D":
                rec_date = QIFParser._parse_date(value)
            elif field == "N":  # Action
                rec_type = _map_qif_action(value)
                rec_is_transfer = value.lower() in _QIF_TRANSFER_ACTIONS
            elif field == "Y":  # Security name
                rec_security = value
            elif field == "Q":  # Quantity
                rec_quantity = Decimal(value.replace(",", "")) if value else Decimal("0")
            elif field == "I":  # Price per share
                rec_price = Decimal(value.replace(",", "")) if value else Decimal("0")
            elif field == "O":  # Commission
                rec_commission = Decimal(value.replace(",", "")) if value else Decimal("0")
            elif field == "T":  # Total amount
                rec_amount = Decimal(value.replace(",", "")) if value else Decimal("0")
            elif field == "M":  # Memo
                rec_memo = value
            elif field == "C":  # Cleared status
                upper = value.upper()
                if upper in ("X", "R"):
                    rec_status = TransactionStatus.RECONCILED
                elif upper in ("C",) or value == "*":
                    rec_status = TransactionStatus.CLEARED
                else:
                    rec_status = TransactionStatus.UNCLEARED
            elif field == "L":  # Linked/transfer account e.g. L[Account Name]
                if value.startswith("[") and value.endswith("]"):
                    rec_linked_account = value[1:-1]
            elif field == "$":  # Cash amount transferred to/from the linked account
                rec_transfer_amount = Decimal(value.replace(",", "")) if value else Decimal("0")

        # File may not end with ^
        _flush()
        return records
