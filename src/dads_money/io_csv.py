"""CSV import/export for transactions."""

import csv
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, TextIO

from .io_qif import InvestmentImportRecord, _map_qif_action
from .models import (
    AccountSummaryReport,
    InvestmentTransaction,
    Transaction,
    TransactionStatus,
    UKTaxReport,
)


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


class InvestmentCSVWriter:
    """Write investment transactions to CSV format."""

    @staticmethod
    def write_file(
        file_path: str,
        transactions: List[InvestmentTransaction],
        security_names: Optional[Dict[str, str]] = None,
    ) -> None:
        """Write investment transactions to a CSV file.

        Args:
            file_path: Destination file path.
            transactions: List of InvestmentTransaction objects.
            security_names: Optional mapping of security_id → name for readable output.
        """
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            InvestmentCSVWriter.write(f, transactions, security_names)

    @staticmethod
    def write(
        file: TextIO,
        transactions: List[InvestmentTransaction],
        security_names: Optional[Dict[str, str]] = None,
    ) -> None:
        """Write investment transactions to CSV format.

        Args:
            file: Writable text file object.
            transactions: List of InvestmentTransaction objects.
            security_names: Optional mapping of security_id → name.
        """
        if security_names is None:
            security_names = {}

        fieldnames = [
            "Date",
            "Action",
            "Security",
            "Quantity",
            "Price",
            "Commission",
            "Amount",
            "Memo",
            "Status",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for txn in transactions:
            security_name = ""
            if txn.security_id:
                security_name = security_names.get(txn.security_id, txn.security_id)

            writer.writerow(
                {
                    "Date": txn.date.strftime("%Y-%m-%d"),
                    "Action": txn.transaction_type.value,
                    "Security": security_name,
                    "Quantity": str(txn.quantity) if txn.quantity else "",
                    "Price": str(txn.price) if txn.price else "",
                    "Commission": str(txn.commission) if txn.commission else "",
                    "Amount": str(txn.amount),
                    "Memo": txn.memo,
                    "Status": (
                        txn.status.value if txn.status != TransactionStatus.UNCLEARED else ""
                    ),
                }
            )


class AccountSummaryCSVWriter:
    """Write an AccountSummaryReport as an Excel-friendly CSV file.

    Amounts are written as plain numbers (no currency symbols or thousands
    separators) so Excel treats them as numeric, dates use ISO YYYY-MM-DD
    format, and files are encoded as UTF-8 with a BOM so Excel decodes
    non-ASCII names correctly.
    """

    _OVERVIEW_HEADER: List[str] = [
        "Account",
        "Type",
        "Opening Balance",
        "Credits",
        "Debits",
        "Net Change",
        "Closing Balance",
        "Transactions",
    ]

    @staticmethod
    def write_file(file_path: str, report: AccountSummaryReport) -> None:
        """Write an account summary report to a CSV file.

        Args:
            file_path: Destination file path.
            report: The report to export.
        """
        with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
            AccountSummaryCSVWriter.write(f, report)

    @staticmethod
    def write(file: TextIO, report: AccountSummaryReport) -> None:
        """Write an account summary report to CSV format.

        Args:
            file: Writable text file object.
            report: The report to export.
        """
        writer = csv.writer(file)

        writer.writerow(["Account Summary Report"])
        writer.writerow(["Period Start", report.start_date.isoformat()])
        writer.writerow(["Period End", report.end_date.isoformat()])
        writer.writerow(["Generated", date.today().isoformat()])
        writer.writerow([])

        # Overview — one row per account plus totals
        writer.writerow(AccountSummaryCSVWriter._OVERVIEW_HEADER)
        for entry in report.entries:
            writer.writerow(
                [
                    entry.account_name,
                    entry.account_type,
                    f"{entry.opening_balance:.2f}",
                    f"{entry.total_credits:.2f}",
                    f"{entry.total_debits:.2f}",
                    f"{entry.net_change:.2f}",
                    f"{entry.closing_balance:.2f}",
                    str(entry.transaction_count),
                ]
            )
        writer.writerow(
            [
                "TOTALS",
                "",
                "",
                f"{report.total_credits:.2f}",
                f"{report.total_debits:.2f}",
                f"{report.net_change:.2f}",
                "",
                str(sum(e.transaction_count for e in report.entries)),
            ]
        )
        writer.writerow([])

        # Category breakdown — aggregated across all accounts
        cat_totals: Dict[str, Decimal] = {}
        for entry in report.entries:
            for row in entry.category_breakdown:
                cat_totals[row.category_name] = (
                    cat_totals.get(row.category_name, Decimal("0")) + row.amount
                )

        income = [(k, v) for k, v in sorted(cat_totals.items()) if v > Decimal("0")]
        expenses = [(k, abs(v)) for k, v in sorted(cat_totals.items()) if v < Decimal("0")]

        writer.writerow(["Income by Category"])
        writer.writerow(["Category", "Amount"])
        if income:
            for cat, amount in income:
                writer.writerow([cat, f"{amount:.2f}"])
            writer.writerow(["Total Income", f"{sum(v for _, v in income):.2f}"])
        else:
            writer.writerow(["(none)"])
        writer.writerow([])

        writer.writerow(["Expenses by Category"])
        writer.writerow(["Category", "Amount"])
        if expenses:
            for cat, amount in expenses:
                writer.writerow([cat, f"{amount:.2f}"])
            writer.writerow(["Total Expenses", f"{sum(v for _, v in expenses):.2f}"])
        else:
            writer.writerow(["(none)"])


def _format_quantity(quantity: Decimal) -> str:
    """Format a share quantity as a plain number without trailing zeros."""
    text = f"{quantity:f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


class UKTaxReportCSVWriter:
    """Write a UKTaxReport as an Excel-friendly CSV file.

    Amounts are written as plain numbers (no pound signs or thousands
    separators), dates use ISO YYYY-MM-DD format, joint shares are plain
    percentages, ISA-exempt rows carry an explicit Yes flag, and files are
    encoded as UTF-8 with a BOM so Excel decodes non-ASCII names correctly.
    """

    @staticmethod
    def write_file(file_path: str, report: UKTaxReport) -> None:
        """Write a UK tax report to a CSV file.

        Args:
            file_path: Destination file path.
            report: The report to export.
        """
        with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
            UKTaxReportCSVWriter.write(f, report)

    @staticmethod
    def write(file: TextIO, report: UKTaxReport) -> None:
        """Write a UK tax report to CSV format.

        Args:
            file: Writable text file object.
            report: The report to export.
        """
        writer = csv.writer(file)

        writer.writerow(["UK Tax Report"])
        writer.writerow(["Tax Year", report.tax_year_label])
        writer.writerow(["Generated", date.today().isoformat()])
        writer.writerow([])

        writer.writerow(["Summary"])
        writer.writerow(["Net Capital Gain / (Loss)", f"{report.net_capital_gain:.2f}"])
        writer.writerow(["Total Dividends (excl. ISA)", f"{report.total_dividends:.2f}"])
        writer.writerow(["Total Interest (excl. ISA)", f"{report.total_interest:.2f}"])
        writer.writerow(["Total Other Income", f"{report.total_other_income:.2f}"])
        writer.writerow([])

        # Capital gains
        writer.writerow(["Capital Gains"])
        writer.writerow(
            [
                "Date",
                "Account",
                "Security",
                "Quantity",
                "Proceeds",
                "Cost",
                "Gain/(Loss)",
                "Share %",
                "ISA Exempt",
            ]
        )
        if report.capital_gains:
            for e in report.capital_gains:
                writer.writerow(
                    [
                        e.date.isoformat(),
                        e.account_name,
                        e.security_name,
                        _format_quantity(e.quantity),
                        f"{e.proceeds:.2f}",
                        f"{e.cost:.2f}",
                        f"{e.gain:.2f}",
                        str(e.share_pct),
                        "Yes" if e.is_isa else "",
                    ]
                )
            writer.writerow(["Total Gains (excl. ISA)", f"{report.total_gains:.2f}"])
            writer.writerow(["Total Losses (excl. ISA)", f"{report.total_losses:.2f}"])
            writer.writerow(["Net Capital Gain", f"{report.net_capital_gain:.2f}"])
        else:
            writer.writerow(["(none)"])
        writer.writerow([])

        # Dividends
        dividends = [
            i
            for i in report.investment_income
            if i.income_type in ("Dividend", "Reinvested Dividend")
        ]
        writer.writerow(["Dividends"])
        writer.writerow(["Date", "Account", "Security", "Type", "Amount", "Share %", "ISA Exempt"])
        if dividends:
            for i in dividends:
                writer.writerow(
                    [
                        i.date.isoformat(),
                        i.account_name,
                        i.security_name,
                        i.income_type,
                        f"{i.amount:.2f}",
                        str(i.share_pct),
                        "Yes" if i.is_isa else "",
                    ]
                )
            writer.writerow(["Total Dividends (excl. ISA)", f"{report.total_dividends:.2f}"])
        else:
            writer.writerow(["(none)"])
        writer.writerow([])

        # Interest — investment interest followed by savings interest
        inv_interest = [
            i
            for i in report.investment_income
            if i.income_type not in ("Dividend", "Reinvested Dividend")
        ]
        writer.writerow(["Interest"])
        writer.writerow(["Date", "Account", "Description", "Amount", "Share %", "ISA Exempt"])
        if inv_interest or report.savings_interest:
            for i in inv_interest:
                desc = f"{i.income_type}: {i.security_name}" if i.security_name else i.income_type
                writer.writerow(
                    [
                        i.date.isoformat(),
                        i.account_name,
                        desc,
                        f"{i.amount:.2f}",
                        str(i.share_pct),
                        "Yes" if i.is_isa else "",
                    ]
                )
            for s in report.savings_interest:
                writer.writerow(
                    [
                        s.date.isoformat(),
                        s.account_name,
                        s.payee or "Savings Interest",
                        f"{s.amount:.2f}",
                        str(s.share_pct),
                        "Yes" if s.is_isa else "",
                    ]
                )
            writer.writerow(["Total Interest (excl. ISA)", f"{report.total_interest:.2f}"])
        else:
            writer.writerow(["(none)"])
        writer.writerow([])

        # Other income
        writer.writerow(["Other Income"])
        writer.writerow(["Date", "Account", "Payee", "Category", "Amount", "Share %"])
        if report.other_income:
            for o in report.other_income:
                writer.writerow(
                    [
                        o.date.isoformat(),
                        o.account_name,
                        o.payee,
                        o.category_name,
                        f"{o.amount:.2f}",
                        str(o.share_pct),
                    ]
                )
            writer.writerow(["Total Other Income", f"{report.total_other_income:.2f}"])
        else:
            writer.writerow(["(none)"])


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
