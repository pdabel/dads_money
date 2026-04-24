"""CSV import/export for transactions."""

import csv
from datetime import datetime, date
from decimal import Decimal
from typing import List, TextIO

from .io_qif import InvestmentImportRecord, _map_qif_action
from .models import Transaction, TransactionStatus


class CSVParser:
    """Parse CSV transaction files."""

    @staticmethod
    def parse_file(file_path: str) -> List[Transaction]:
        """Parse CSV file and return list of transactions."""
        with open(file_path, "r", encoding="utf-8") as f:
            return CSVParser.parse(f)

    @staticmethod
    def parse(file: TextIO) -> List[Transaction]:
        """Parse CSV format from file object."""
        transactions = []
        reader = csv.DictReader(file)

        for row in reader:
            transaction = Transaction()

            # Try common CSV column names (case-insensitive)
            # Filter out None keys that can occur in malformed CSV
            row_lower = {k.lower(): v for k, v in row.items() if k is not None}

            # Date
            if "date" in row_lower:
                transaction.date = CSVParser._parse_date(row_lower["date"])
            elif "transaction date" in row_lower:
                transaction.date = CSVParser._parse_date(row_lower["transaction date"])

            # Amount
            if "amount" in row_lower:
                transaction.amount = CSVParser._parse_amount(row_lower["amount"])
            elif "debit" in row_lower and row_lower["debit"]:
                transaction.amount = -CSVParser._parse_amount(row_lower["debit"])
            elif "credit" in row_lower and row_lower["credit"]:
                transaction.amount = CSVParser._parse_amount(row_lower["credit"])

            # Payee/Description
            if "payee" in row_lower:
                transaction.payee = row_lower["payee"]
            elif "description" in row_lower:
                transaction.payee = row_lower["description"]
            elif "merchant" in row_lower:
                transaction.payee = row_lower["merchant"]

            # Memo
            if "memo" in row_lower:
                transaction.memo = row_lower["memo"]
            elif "notes" in row_lower:
                transaction.memo = row_lower["notes"]

            # Check number
            if "check number" in row_lower:
                transaction.check_number = row_lower["check number"]
            elif "check" in row_lower:
                transaction.check_number = row_lower["check"]

            transactions.append(transaction)

        return transactions

    @staticmethod
    def _parse_date(date_str: str) -> date:
        """Parse various date formats."""
        if not date_str:
            return datetime.now().date()

        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%Y%m%d"]:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return datetime.now().date()

    @staticmethod
    def _parse_amount(amount_str: str) -> Decimal:
        """Parse amount string to Decimal."""
        if not amount_str:
            return Decimal("0.00")

        # Remove common currency symbols, commas, and whitespace
        cleaned = amount_str
        # Remove various currency symbols
        for symbol in [
            "$",
            "€",
            "£",
            "¥",
            "₹",
            "₽",
            "₩",
            "Fr",
            "kr",
            "R",
            "C$",
            "A$",
            "MX$",
            "NZ$",
            "S$",
            "HK$",
        ]:
            cleaned = cleaned.replace(symbol, "")
        # Remove thousands separators and whitespace
        cleaned = cleaned.replace(",", "").replace(" ", "").strip()

        # Handle parentheses as negative
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]

        try:
            return Decimal(cleaned)
        except:
            return Decimal("0.00")


class CSVWriter:
    """Write transactions to CSV format."""

    @staticmethod
    def write_file(file_path: str, transactions: List[Transaction]) -> None:
        """Write transactions to CSV file."""
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            CSVWriter.write(f, transactions)

    @staticmethod
    def write(file: TextIO, transactions: List[Transaction]) -> None:
        """Write transactions to CSV format."""
        fieldnames = ["Date", "Payee", "Memo", "Amount", "Status", "Check Number"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        writer.writeheader()
        for trans in transactions:
            writer.writerow(
                {
                    "Date": trans.date.strftime("%Y-%m-%d"),
                    "Payee": trans.payee,
                    "Memo": trans.memo,
                    "Amount": str(trans.amount),
                    "Status": (
                        trans.status.value if trans.status != TransactionStatus.UNCLEARED else ""
                    ),
                    "Check Number": trans.check_number,
                }
            )


# ---------------------------------------------------------------------------
# Investment CSV support
# ---------------------------------------------------------------------------

_INV_HEADER_COLS = {"security", "action", "type", "shares", "quantity"}


class InvestmentCSVParser:
    """Parse CSV files that contain investment transaction data."""

    @staticmethod
    def is_investment_csv(file_path: str) -> bool:
        """Return True when the CSV headers look like investment data."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                headers = {h.strip().lower() for h in next(reader, [])}
            return bool(headers & _INV_HEADER_COLS)
        except (OSError, StopIteration):
            return False

    @staticmethod
    def parse_file(file_path: str) -> List[InvestmentImportRecord]:
        with open(file_path, "r", encoding="utf-8") as f:
            return InvestmentCSVParser.parse(f)

    @staticmethod
    def parse(file: TextIO) -> List[InvestmentImportRecord]:
        records: List[InvestmentImportRecord] = []
        reader = csv.DictReader(file)
        for row in reader:
            r = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}

            # Date
            raw_date = r.get("date") or r.get("transaction date") or ""
            rec_date = CSVParser._parse_date(raw_date) if raw_date else datetime.now().date()

            # Transaction type
            action_str = r.get("action") or r.get("type") or ""
            rec_type = _map_qif_action(action_str) if action_str else None

            # Security
            rec_security = r.get("security") or r.get("security name") or ""

            # Quantity
            rec_quantity = _parse_decimal(r.get("shares") or r.get("quantity") or "0")

            # Price
            rec_price = _parse_decimal(r.get("price") or "0")

            # Commission
            rec_commission = _parse_decimal(r.get("commission") or r.get("fee") or "0")

            # Amount
            rec_amount = _parse_decimal(r.get("amount") or "0")

            # Memo
            rec_memo = r.get("memo") or r.get("notes") or ""

            # Status
            status_str = (r.get("status") or r.get("cleared") or "").upper()
            if status_str in ("X", "R", "RECONCILED"):
                rec_status = TransactionStatus.RECONCILED
            elif status_str in ("C", "*", "CLEARED"):
                rec_status = TransactionStatus.CLEARED
            else:
                rec_status = TransactionStatus.UNCLEARED

            # Infer type from amount sign when not explicitly provided
            if rec_type is None:
                from .models import InvestmentTransactionType  # avoid circular at module level

                rec_type = (
                    InvestmentTransactionType.BUY
                    if rec_amount <= Decimal("0")
                    else InvestmentTransactionType.MISC_INC
                )

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
                )
            )
        return records


def _parse_decimal(value: str) -> Decimal:
    """Strip currency symbols and parse a string to Decimal."""
    cleaned = value
    for sym in ("$", "€", "£", "¥", "₹", "₽", "₩", "Fr", "kr"):
        cleaned = cleaned.replace(sym, "")
    cleaned = cleaned.replace(",", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return Decimal(cleaned)
    except Exception:
        return Decimal("0")
