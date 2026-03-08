"""QIF (Quicken Interchange Format) import/export."""

from datetime import datetime
from decimal import Decimal
from io import StringIO
from typing import List, TextIO

from .models import Transaction, TransactionStatus


class QIFParser:
    """Parse QIF format files."""

    @staticmethod
    def parse_file(file_path: str) -> List[Transaction]:
        """Parse QIF file and return list of transactions."""
        with open(file_path, "r", encoding="utf-8") as f:
            return QIFParser.parse(f)

    @staticmethod
    def parse(file: TextIO) -> List[Transaction]:
        """Parse QIF format from file object."""
        transactions = []
        current_transaction = None

        for line in file:
            line = line.strip()
            if not line:
                continue

            if line == "!Type:Bank" or line == "!Type:Cash" or line == "!Type:CCard":
                # Account type header - just continue
                continue

            if line == "^":
                # End of transaction
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
                # Remove commas and parse as decimal
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
                # Transfer accounts are enclosed in brackets: [Account Name]
                if field_value.startswith("[") and field_value.endswith("]"):
                    # This is a transfer - we'll handle this later when we have account mapping
                    current_transaction.memo += f" [Transfer: {field_value[1:-1]}]"
                # else it's a category - we'll need to map this later

        # Don't forget last transaction if file doesn't end with ^
        if current_transaction:
            transactions.append(current_transaction)

        return transactions

    @staticmethod
    def _parse_date(date_str: str) -> datetime.date:
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
    def write_file(file_path: str, transactions: List[Transaction], account_type: str = "Bank"):
        """Write transactions to QIF file."""
        with open(file_path, "w", encoding="utf-8") as f:
            QIFWriter.write(f, transactions, account_type)

    @staticmethod
    def write(file: TextIO, transactions: List[Transaction], account_type: str = "Bank"):
        """Write transactions to QIF format."""
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

            # Category (simplified - would need category name lookup)
            # For now, skip category in export

            # End of transaction
            file.write("^\n")
