"""Account and transaction dialogs."""

from datetime import date
from decimal import Decimal
from typing import Any, List, Optional

from PySide6.QtCore import QDate, QLocale
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
)

from ..models import (
    Account,
    AccountType,
    SavingsAccountType,
    Transaction,
    TransactionStatus,
)
from ..services import MoneyService
from ..settings import get_settings


class AccountDialog(QDialog):
    """Dialog for creating/editing accounts."""

    def __init__(self, parent: Any, account: Optional[Account] = None) -> None:
        super().__init__(parent)
        self.account = account
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize dialog UI."""
        self.setWindowTitle("Account" if not self.account else "Edit Account")
        self.setModal(True)

        layout = QFormLayout()

        # Name
        self.name_edit = QLineEdit()
        if self.account:
            self.name_edit.setText(self.account.name)
        layout.addRow("Account Name:", self.name_edit)

        # Type
        self.type_combo = QComboBox()
        for acc_type in AccountType:
            self.type_combo.addItem(acc_type.value, acc_type)
        if self.account:
            index = self.type_combo.findData(self.account.account_type)
            self.type_combo.setCurrentIndex(index)
        self.type_combo.currentIndexChanged.connect(self._on_account_type_changed)
        layout.addRow("Account Type:", self.type_combo)

        # Savings Subtype (shown only for savings accounts)
        self.subtype_label = QLabel("Savings Type:")
        self.subtype_combo = QComboBox()
        for subtype in SavingsAccountType:
            self.subtype_combo.addItem(subtype.value, subtype)
        if self.account and self.account.savings_subtype:
            index = self.subtype_combo.findData(self.account.savings_subtype)
            self.subtype_combo.setCurrentIndex(index)
        layout.addRow(self.subtype_label, self.subtype_combo)

        # Opening balance
        self.balance_spin = QDoubleSpinBox()
        self.balance_spin.setRange(-1000000, 1000000)
        settings = get_settings()
        self.balance_spin.setDecimals(settings.decimal_places)
        self.balance_spin.setLocale(QLocale.c())
        self.balance_spin.setPrefix(settings.currency_symbol + " ")
        if self.account:
            self.balance_spin.setValue(float(self.account.opening_balance))
        layout.addRow("Opening Balance:", self.balance_spin)

        # Owner
        self.owner_edit = QLineEdit()
        self.owner_edit.setPlaceholderText("e.g. Alice, Bob, Joint (optional)")
        if self.account:
            self.owner_edit.setText(self.account.owner)
        layout.addRow("Owner:", self.owner_edit)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # type: ignore[attr-defined]
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

        # Set initial visibility
        self._on_account_type_changed()

    def _on_account_type_changed(self) -> None:
        """Show/hide savings subtype based on account type."""
        is_savings = self.type_combo.currentData() == AccountType.SAVINGS
        self.subtype_label.setVisible(is_savings)
        self.subtype_combo.setVisible(is_savings)

    def get_data(self) -> dict[str, Any]:
        """Get dialog data."""
        savings_subtype = None
        if self.type_combo.currentData() == AccountType.SAVINGS:
            savings_subtype = self.subtype_combo.currentData()

        return {
            "name": self.name_edit.text(),
            "type": self.type_combo.currentData(),
            "savings_subtype": savings_subtype,
            "opening_balance": Decimal(str(self.balance_spin.value())),
            "owner": self.owner_edit.text().strip(),
        }


class TransactionDialog(QDialog):
    """Dialog for creating/editing transactions."""

    def __init__(
        self,
        parent: Any,
        service: MoneyService,
        account: Account,
        transaction: Optional[Transaction] = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.account = account
        self.transaction = transaction
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize dialog UI."""
        self.setWindowTitle("New Transaction" if not self.transaction else "Edit Transaction")
        self.setModal(True)
        self.setMinimumWidth(400)

        layout = QFormLayout()
        self._layout = layout

        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat(get_settings().qt_date_format)
        if self.transaction:
            self.date_edit.setDate(
                QDate(
                    self.transaction.date.year,
                    self.transaction.date.month,
                    self.transaction.date.day,
                )
            )
        else:
            self.date_edit.setDate(QDate.currentDate())
        layout.addRow("Date:", self.date_edit)

        # Transaction type
        self.type_combo = QComboBox()
        self.type_combo.addItem("Deposit", "deposit")
        self.type_combo.addItem("Payment", "payment")
        self.type_combo.addItem("Transfer", "transfer")

        # Add savings-specific transaction types
        if self.account.account_type == AccountType.SAVINGS:
            self.type_combo.addItem("Interest", "interest")
            if self.account.savings_subtype == SavingsAccountType.STOCKS_SHARES_ISA:
                self.type_combo.addItem("Dividend", "dividend")

        if self.transaction and self.transaction.transfer_account_id:
            self.type_combo.setCurrentIndex(self.type_combo.findData("transfer"))
        elif self.transaction and self.transaction.amount >= 0:
            self.type_combo.setCurrentIndex(0)
        else:
            self.type_combo.setCurrentIndex(1)

        # Connect signal to update payee when type changes
        self.type_combo.currentIndexChanged.connect(self._on_transaction_type_changed)

        layout.addRow("Type:", self.type_combo)

        # Transfer destination — shown only when type == "transfer"
        self._transfer_accounts: List[Account] = [
            a
            for a in self.service.get_all_accounts()
            if a.id != self.account.id and a.account_type != AccountType.INVESTMENT
        ]
        self._transfer_label = QLabel("Transfer to:")
        self.transfer_combo = QComboBox()
        for acct in self._transfer_accounts:
            self.transfer_combo.addItem(acct.name, acct.id)
        if self.transaction and self.transaction.transfer_account_id:
            idx = self.transfer_combo.findData(self.transaction.transfer_account_id)
            if idx >= 0:
                self.transfer_combo.setCurrentIndex(idx)
        layout.addRow(self._transfer_label, self.transfer_combo)

        # Payee - editable combo box with predefined and historical payees
        self._payee_label = QLabel("Payee:")
        self.payee_combo = QComboBox()
        self.payee_combo.setEditable(True)
        self.payee_combo.setInsertPolicy(QComboBox.NoInsert)  # type: ignore[attr-defined]

        # Load all payees (predefined + historical from transactions)
        all_payees = self.service.get_all_payees()
        self.payee_combo.addItems(all_payees)

        if self.transaction:
            self.payee_combo.setEditText(self.transaction.payee)

        layout.addRow(self._payee_label, self.payee_combo)

        # Amount
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 1000000)
        settings = get_settings()
        self.amount_spin.setDecimals(settings.decimal_places)
        self.amount_spin.setLocale(QLocale.c())
        self.amount_spin.setPrefix(settings.currency_symbol + " ")
        if self.transaction:
            self.amount_spin.setValue(abs(float(self.transaction.amount)))
        else:
            self.amount_spin.setValue(0.01)
        layout.addRow("Amount:", self.amount_spin)

        # Status
        self.status_combo = QComboBox()
        self.status_combo.addItem("Uncleared", TransactionStatus.UNCLEARED)
        self.status_combo.addItem("Cleared", TransactionStatus.CLEARED)
        self.status_combo.addItem("Reconciled", TransactionStatus.RECONCILED)
        if self.transaction:
            index = self.status_combo.findData(self.transaction.status)
            self.status_combo.setCurrentIndex(index)
        layout.addRow("Status:", self.status_combo)

        # Memo
        self.memo_edit = QLineEdit()
        if self.transaction:
            self.memo_edit.setText(self.transaction.memo)
        layout.addRow("Memo:", self.memo_edit)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # type: ignore[attr-defined]
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self.setLayout(layout)

        # Apply initial visibility based on current type
        self._update_transfer_visibility()

    def _update_transfer_visibility(self) -> None:
        """Show/hide transfer-specific and payee rows depending on transaction type."""
        is_transfer = self.type_combo.currentData() == "transfer"
        self._transfer_label.setVisible(is_transfer)
        self.transfer_combo.setVisible(is_transfer)
        self._payee_label.setVisible(not is_transfer)
        self.payee_combo.setVisible(not is_transfer)

    def _on_transaction_type_changed(self) -> None:
        """Handle transaction type change to auto-populate fields."""
        trans_type = self.type_combo.currentData()
        self._update_transfer_visibility()

        # Auto-populate payee for interest and dividend types
        if trans_type == "interest":
            self.payee_combo.setEditText("Interest Payment")
        elif trans_type == "dividend":
            self.payee_combo.setEditText("Dividend Payment")
        elif trans_type in ("deposit", "payment"):
            if self.payee_combo.currentText() in ["Interest Payment", "Dividend Payment"]:
                self.payee_combo.clearEditText()

    def get_data(self) -> dict[str, Any]:
        """Get dialog data."""
        qdate = self.date_edit.date()
        amount = Decimal(str(self.amount_spin.value()))
        trans_type = self.type_combo.currentData()

        if trans_type == "transfer":
            transfer_account_id = self.transfer_combo.currentData()
            return {
                "type": "transfer",
                "date": date(qdate.year(), qdate.month(), qdate.day()),
                "transfer_account_id": transfer_account_id,
                "amount": amount,
                "status": self.status_combo.currentData(),
                "memo": self.memo_edit.text(),
            }

        # Payment types are negative, all others are positive
        if trans_type == "payment":
            amount = -amount

        return {
            "type": trans_type,
            "date": date(qdate.year(), qdate.month(), qdate.day()),
            "payee": self.payee_combo.currentText(),
            "amount": amount,
            "status": self.status_combo.currentData(),
            "memo": self.memo_edit.text(),
        }
