"""Microsoft Money 3.0-style desktop UI."""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QDate, QTime, QThread, Signal
from PySide6.QtGui import QAction, QFont, QColor
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QDialog,
    QLineEdit,
    QComboBox,
    QDateEdit,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QHeaderView,
    QDialogButtonBox,
    QFormLayout,
    QDoubleSpinBox,
    QCheckBox,
    QGroupBox,
    QProgressBar,
)

from .config import Config
from .models import (
    Account,
    AccountType,
    SavingsAccountType,
    Transaction,
    TransactionStatus,
    Category,
    Security,
    SecurityType,
    SecurityPrice,
    InvestmentTransaction,
    InvestmentTransactionType,
    Holding,
)
from .services import MoneyService, _QUANTITY_TYPES
from .settings import get_settings, CURRENCIES


class MainWindow(QMainWindow):
    """Main application window with Money 3.0 style interface."""

    REGISTER_COLUMNS = ["Date", "Payee", "Memo", "Status", "Credit", "Debit", "Balance"]

    def __init__(self, db_path: Optional[Path] = None):
        super().__init__()
        self.settings = get_settings()
        self.current_db_path = db_path if db_path else Config.get_database_path()
        self.service = MoneyService(self.current_db_path)
        self.current_account: Optional[Account] = None
        self.init_ui()
        self.load_accounts()
        self._add_to_recent_databases(self.current_db_path)
        self._update_window_title()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.setGeometry(100, 100, 1200, 700)

        # Create menu bar
        self.create_menus()

        # Create toolbar
        self.create_toolbar()

        # Create main widget with splitter
        central = QWidget()
        main_layout = QHBoxLayout()

        # Create splitter for accounts and register
        self.splitter = QSplitter(Qt.Horizontal)  # type: ignore[attr-defined]

        # Left panel - Account list
        left_panel = self.create_account_panel()
        self.splitter.addWidget(left_panel)

        # Right panel - stacked so we can swap register vs investment panel
        self.right_stack = QStackedWidget()
        self.register_panel = self.create_register_panel()
        self.right_stack.addWidget(self.register_panel)  # index 0
        self.splitter.addWidget(self.right_stack)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)

        main_layout.addWidget(self.splitter)
        central.setLayout(main_layout)
        self.setCentralWidget(central)

        # Status bar
        self.statusBar().showMessage("Ready")

    def create_menus(self) -> None:
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_db_action = QAction("&New Database...", self)
        new_db_action.triggered.connect(self.new_database)
        file_menu.addAction(new_db_action)

        open_db_action = QAction("&Open Database...", self)
        open_db_action.triggered.connect(self.open_database)
        file_menu.addAction(open_db_action)

        self.recent_menu = file_menu.addMenu("Recent &Databases")
        self._update_recent_databases_menu()

        file_menu.addSeparator()

        new_account_action = QAction("&New Account...", self)
        new_account_action.triggered.connect(self.new_account)
        file_menu.addAction(new_account_action)

        file_menu.addSeparator()

        import_action = QAction("&Import...", self)
        import_action.triggered.connect(self.import_transactions)
        file_menu.addAction(import_action)

        export_action = QAction("&Export...", self)
        export_action.triggered.connect(self.export_transactions)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        new_trans_action = QAction("New &Transaction", self)
        new_trans_action.triggered.connect(self.new_transaction)
        edit_menu.addAction(new_trans_action)

        edit_menu.addSeparator()

        categories_action = QAction("&Categories...", self)
        categories_action.triggered.connect(self.manage_categories)
        edit_menu.addAction(categories_action)

        payees_action = QAction("&Payees...", self)
        payees_action.triggered.connect(self.manage_payees)
        edit_menu.addAction(payees_action)

        edit_menu.addSeparator()

        settings_action = QAction("&Settings...", self)
        settings_action.triggered.connect(self.show_settings)
        edit_menu.addAction(settings_action)

        # View menu
        view_menu = menubar.addMenu("&View")
        columns_action = QAction("Register &Columns...", self)
        columns_action.triggered.connect(self.choose_register_columns)
        view_menu.addAction(columns_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self) -> None:
        """Create toolbar."""
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)

        new_account_btn = QPushButton("New Account")
        new_account_btn.clicked.connect(self.new_account)
        toolbar.addWidget(new_account_btn)

        new_trans_btn = QPushButton("New Transaction")
        new_trans_btn.clicked.connect(self.new_transaction)
        toolbar.addWidget(new_trans_btn)

        toolbar.addSeparator()

        import_btn = QPushButton("Import")
        import_btn.clicked.connect(self.import_transactions)
        toolbar.addWidget(import_btn)

        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self.export_transactions)
        toolbar.addWidget(export_btn)

    def create_account_panel(self) -> QWidget:
        """Create the account list panel."""
        panel = QWidget()
        layout = QVBoxLayout()

        # Title
        title = QLabel("Accounts")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title.setFont(title_font)
        layout.addWidget(title)

        # Account list
        self.account_list = QListWidget()
        self.account_list.currentRowChanged.connect(self.account_selected)
        layout.addWidget(self.account_list)

        # Buttons
        btn_layout = QHBoxLayout()
        new_btn = QPushButton("New")
        new_btn.clicked.connect(self.new_account)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self.edit_account)
        btn_layout.addWidget(new_btn)
        btn_layout.addWidget(edit_btn)
        layout.addLayout(btn_layout)

        panel.setLayout(layout)
        return panel

    def create_register_panel(self) -> QWidget:
        """Create the transaction register panel."""
        panel = QWidget()
        layout = QVBoxLayout()

        # Account info header
        self.account_header = QLabel("Select an account")
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(11)
        self.account_header.setFont(header_font)
        layout.addWidget(self.account_header)

        # Balance display
        self.balance_label = QLabel("")
        layout.addWidget(self.balance_label)

        # Transaction table
        self.transaction_table = QTableWidget()
        self.transaction_table.setColumnCount(len(self.REGISTER_COLUMNS))
        self.transaction_table.setHorizontalHeaderLabels(self.REGISTER_COLUMNS)
        self.transaction_table.horizontalHeader().setStretchLastSection(False)
        self.transaction_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)  # type: ignore[attr-defined]
        self.transaction_table.setSelectionBehavior(QTableWidget.SelectRows)  # type: ignore[attr-defined]
        self.transaction_table.doubleClicked.connect(self.edit_transaction)
        self.apply_register_column_visibility()
        layout.addWidget(self.transaction_table)

        # Buttons
        btn_layout = QHBoxLayout()
        new_btn = QPushButton("New Transaction")
        new_btn.clicked.connect(self.new_transaction)
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self.edit_transaction)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_transaction)
        btn_layout.addWidget(new_btn)
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        panel.setLayout(layout)
        return panel

    def apply_register_column_visibility(self) -> None:
        """Apply register column visibility from user settings."""
        default_visible = list(range(len(self.REGISTER_COLUMNS)))
        stored_visible = self.settings.get("register_visible_columns", default_visible)
        stored_column_count = self.settings.get("register_column_count", len(self.REGISTER_COLUMNS))

        # Reset to defaults if the number of columns has changed (e.g., Check # was removed)
        if stored_column_count != len(self.REGISTER_COLUMNS):
            stored_visible = default_visible
            self.settings.set("register_visible_columns", default_visible)
            self.settings.set("register_column_count", len(self.REGISTER_COLUMNS))
            self.settings.save()

        if not isinstance(stored_visible, list) or not stored_visible:
            stored_visible = default_visible

        visible_columns = set()
        for col in stored_visible:
            try:
                col_index = int(col)
                if 0 <= col_index < len(self.REGISTER_COLUMNS):
                    visible_columns.add(col_index)
            except (TypeError, ValueError):
                continue

        if not visible_columns:
            visible_columns = set(default_visible)

        for column_index in range(len(self.REGISTER_COLUMNS)):
            self.transaction_table.setColumnHidden(
                column_index, column_index not in visible_columns
            )

    def choose_register_columns(self) -> None:
        """Allow user to choose which register columns are visible."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Register Columns")
        dialog.setModal(True)

        layout = QVBoxLayout()
        checkboxes = []

        for column_index, column_name in enumerate(self.REGISTER_COLUMNS):
            checkbox = QCheckBox(column_name)
            checkbox.setChecked(not self.transaction_table.isColumnHidden(column_index))
            checkboxes.append(checkbox)
            layout.addWidget(checkbox)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # type: ignore[attr-defined]
        reset_button = buttons.addButton("Reset to Default", QDialogButtonBox.ResetRole)  # type: ignore[attr-defined]

        def save_columns() -> None:
            visible_columns = [
                index for index, checkbox in enumerate(checkboxes) if checkbox.isChecked()
            ]

            if not visible_columns:
                QMessageBox.warning(
                    dialog, "No Columns Selected", "Please select at least one column."
                )
                return

            self.settings.set("register_visible_columns", visible_columns)
            self.settings.set("register_column_count", len(self.REGISTER_COLUMNS))
            self.settings.save()
            self.apply_register_column_visibility()
            dialog.accept()

        def reset_columns() -> None:
            for checkbox in checkboxes:
                checkbox.setChecked(True)
            default_visible = list(range(len(self.REGISTER_COLUMNS)))
            self.settings.set("register_visible_columns", default_visible)
            self.settings.set("register_column_count", len(self.REGISTER_COLUMNS))
            self.settings.save()
            self.apply_register_column_visibility()

        buttons.accepted.connect(save_columns)
        buttons.rejected.connect(dialog.reject)
        reset_button.clicked.connect(reset_columns)
        layout.addWidget(buttons)

        dialog.setLayout(layout)
        dialog.exec()

    def load_accounts(self, selected_account_id: Optional[str] = None) -> None:
        """Load accounts into the list."""
        if selected_account_id is None and self.current_account:
            selected_account_id = self.current_account.id

        self.account_list.clear()
        accounts = self.service.get_all_accounts()
        selected_index = -1

        for index, account in enumerate(accounts):
            # Determine account type display
            account_type_display = account.account_type.value
            if account.account_type == AccountType.SAVINGS and account.savings_subtype:
                account_type_display = account.savings_subtype.value

            balance_str = self.settings.format_currency(account.current_balance)
            item = QListWidgetItem(f"{account.name} ({account_type_display}) - {balance_str}")
            item.setData(Qt.UserRole, account.id)  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            self.account_list.addItem(item)
            if account.id == selected_account_id:
                selected_index = index

        if accounts:
            self.account_list.setCurrentRow(selected_index if selected_index >= 0 else 0)
        else:
            self.current_account = None

    def account_selected(self, index: int) -> None:
        """Handle account selection."""
        if index < 0:
            return

        selected_item = self.account_list.item(index)
        if not selected_item:
            return

        account_id = selected_item.data(Qt.UserRole)  # type: ignore[attr-defined]
        if not account_id:
            return

        account = self.service.get_account(account_id)
        if not account:
            return

        self.current_account = account
        self._update_right_panel()

    def _update_right_panel(self) -> None:
        """Swap the right panel depending on the current account type."""
        if self.current_account is None:
            self.right_stack.setCurrentIndex(0)
            return

        if self.current_account.account_type == AccountType.INVESTMENT:
            # Remove any stale investment panel (index 1 onwards)
            while self.right_stack.count() > 1:
                old = self.right_stack.widget(1)
                if old is not None:
                    self.right_stack.removeWidget(old)
                    old.deleteLater()
            inv_panel = InvestmentPanel(self, self.service, self.current_account, self.settings)
            self.right_stack.addWidget(inv_panel)  # index 1
            self.right_stack.setCurrentIndex(1)
        else:
            # Remove any investment panel and show register
            while self.right_stack.count() > 1:
                old = self.right_stack.widget(1)
                if old is not None:
                    self.right_stack.removeWidget(old)
                    old.deleteLater()
            self.right_stack.setCurrentIndex(0)
            self.load_transactions()

    def load_transactions(self) -> None:
        """Load transactions for current account."""
        if not self.current_account:
            return

        # Build account type display string
        account_type_display = self.current_account.account_type.value
        if (
            self.current_account.account_type == AccountType.SAVINGS
            and self.current_account.savings_subtype
        ):
            account_type_display = self.current_account.savings_subtype.value

        self.account_header.setText(f"{self.current_account.name} - {account_type_display}")
        balance_formatted = self.settings.format_currency(self.current_account.current_balance)
        self.balance_label.setText(f"Current Balance: {balance_formatted}")

        transactions = self.service.get_transactions_for_account(self.current_account.id)
        transactions = sorted(transactions, key=lambda t: (t.date, t.created_date))
        running_balance = self.current_account.opening_balance

        self.transaction_table.setRowCount(len(transactions) + 1)

        opening_date = self.current_account.created_date.strftime(self.settings.date_format)
        self.transaction_table.setItem(0, 0, QTableWidgetItem(opening_date))
        self.transaction_table.setItem(0, 1, QTableWidgetItem("Opening Balance"))
        self.transaction_table.setItem(0, 2, QTableWidgetItem(""))
        self.transaction_table.setItem(0, 3, QTableWidgetItem(""))
        self.transaction_table.setItem(0, 4, QTableWidgetItem(""))
        self.transaction_table.setItem(0, 5, QTableWidgetItem(""))
        opening_balance_item = QTableWidgetItem(self.settings.format_currency(running_balance))
        opening_balance_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[attr-defined]
        self.transaction_table.setItem(0, 6, opening_balance_item)

        for i, trans in enumerate(transactions, start=1):
            date_formatted = trans.date.strftime(self.settings.date_format)
            self.transaction_table.setItem(i, 0, QTableWidgetItem(date_formatted))
            self.transaction_table.setItem(i, 1, QTableWidgetItem(trans.payee))
            self.transaction_table.setItem(i, 2, QTableWidgetItem(trans.memo))

            status_text = ""
            if trans.status == TransactionStatus.RECONCILED:
                status_text = "R"
            elif trans.status == TransactionStatus.CLEARED:
                status_text = "C"
            self.transaction_table.setItem(i, 3, QTableWidgetItem(status_text))

            credit_text = ""
            debit_text = ""
            if trans.amount >= 0:
                credit_text = self.settings.format_currency(trans.amount)
            else:
                debit_text = self.settings.format_currency(abs(trans.amount))

            credit_item = QTableWidgetItem(credit_text)
            credit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[attr-defined]
            if credit_text:  # Only set color if there's a value
                credit_item.setForeground(QColor(0, 128, 0))  # Dark green for credits
            self.transaction_table.setItem(i, 4, credit_item)

            debit_item = QTableWidgetItem(debit_text)
            debit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[attr-defined]
            if debit_text:  # Only set color if there's a value
                debit_item.setForeground(QColor(200, 0, 0))  # Red for debits
            self.transaction_table.setItem(i, 5, debit_item)

            running_balance += trans.amount
            balance_formatted = self.settings.format_currency(running_balance)
            balance_item = QTableWidgetItem(balance_formatted)
            balance_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[attr-defined]
            self.transaction_table.setItem(i, 6, balance_item)

            # Store transaction ID in first column for reference
            item = self.transaction_table.item(i, 0)
            if item:
                item.setData(Qt.UserRole, trans.id)  # type: ignore[attr-defined]

    def new_account(self) -> None:
        """Create a new account."""
        dialog = AccountDialog(self)
        if dialog.exec() == QDialog.Accepted:  # type: ignore[attr-defined]  # type: ignore[attr-defined]
            account_data = dialog.get_data()
            account = self.service.create_account(
                name=account_data["name"],
                account_type=account_data["type"],
                savings_subtype=account_data.get("savings_subtype"),
                opening_balance=account_data["opening_balance"],
            )
            self.load_accounts(account.id)
            self.statusBar().showMessage(f"Account '{account_data['name']}' created")

    def edit_account(self) -> None:
        """Edit the selected account."""
        if not self.current_account:
            QMessageBox.warning(self, "No Account", "Please select an account to edit.")
            return

        dialog = AccountDialog(self, self.current_account)
        if dialog.exec() == QDialog.Accepted:  # type: ignore[attr-defined]
            account_data = dialog.get_data()
            self.current_account.name = account_data["name"]
            self.current_account.account_type = account_data["type"]
            self.current_account.savings_subtype = account_data.get("savings_subtype")
            self.current_account.opening_balance = account_data["opening_balance"]
            self.service.update_account(self.current_account)
            self.load_accounts(self.current_account.id)
            self.statusBar().showMessage(f"Account '{account_data['name']}' updated")

    def new_transaction(self) -> None:
        """Create a new transaction."""
        if not self.current_account:
            QMessageBox.warning(self, "No Account", "Please select an account first.")
            return

        if self.current_account is None:
            return

        dialog = TransactionDialog(self, self.service, self.current_account)
        if dialog.exec() == QDialog.Accepted:  # type: ignore[attr-defined]
            trans_data = dialog.get_data()
            trans = Transaction(
                account_id=self.current_account.id,
                date=trans_data["date"],
                payee=trans_data["payee"],
                memo=trans_data["memo"],
                amount=trans_data["amount"],
                status=trans_data["status"],
            )
            self.service.update_transaction(trans)
            self.load_accounts(self.current_account.id)  # Refresh balance and keep selection
            self.statusBar().showMessage("Transaction created")

    def edit_transaction(self) -> None:
        """Edit the selected transaction."""
        row = self.transaction_table.currentRow()
        if row < 0:
            return

        item = self.transaction_table.item(row, 0)
        if not item:
            return

        trans_id = item.data(Qt.UserRole)  # type: ignore[attr-defined]
        transaction = self.service.get_transaction(trans_id)

        if transaction:
            if self.current_account is None:
                return
            dialog = TransactionDialog(self, self.service, self.current_account, transaction)
            if dialog.exec() == QDialog.Accepted:  # type: ignore[attr-defined]
                trans_data = dialog.get_data()
                transaction.date = trans_data["date"]
                transaction.payee = trans_data["payee"]
                transaction.memo = trans_data["memo"]
                transaction.amount = trans_data["amount"]
                transaction.status = trans_data["status"]
                self.service.update_transaction(transaction)
                self.load_accounts(self.current_account.id)
                self.statusBar().showMessage("Transaction updated")

    def delete_transaction(self) -> None:
        """Delete the selected transaction."""
        row = self.transaction_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a transaction to delete.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this transaction?",
            QMessageBox.Yes | QMessageBox.No,  # type: ignore[attr-defined]
        )

        if reply == QMessageBox.Yes:  # type: ignore[attr-defined]
            item = self.transaction_table.item(row, 0)
            if not item:
                return
            if self.current_account is None:
                return
            trans_id = item.data(Qt.UserRole)  # type: ignore[attr-defined]
            self.service.delete_transaction(trans_id, self.current_account.id)
            self.load_accounts(self.current_account.id)
            self.statusBar().showMessage("Transaction deleted")

    def import_transactions(self) -> None:
        """Import transactions from file."""
        if not self.current_account:
            QMessageBox.warning(self, "No Account", "Please select an account first.")
            return

        file_path, filter_type = QFileDialog.getOpenFileName(
            self,
            "Import Transactions",
            str(Path.home()),
            "QIF Files (*.qif);;CSV Files (*.csv);;OFX Files (*.ofx);;All Files (*.*)",
        )

        if not file_path:
            return

        try:
            count = 0
            if file_path.endswith(".qif"):
                count = self.service.import_qif(file_path, self.current_account.id)
            elif file_path.endswith(".csv"):
                count = self.service.import_csv(file_path, self.current_account.id)
            elif file_path.endswith(".ofx"):
                count = self.service.import_ofx(file_path, self.current_account.id)
            else:
                QMessageBox.warning(
                    self, "Unknown Format", "Please select a QIF, CSV, or OFX file."
                )
                return

            self.load_accounts(self.current_account.id)
            QMessageBox.information(self, "Import Complete", f"Imported {count} transactions.")
            self.statusBar().showMessage(f"Imported {count} transactions")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Error importing file:\n{str(e)}")

    def export_transactions(self) -> None:
        """Export transactions to file."""
        if not self.current_account:
            QMessageBox.warning(self, "No Account", "Please select an account first.")
            return

        file_path, filter_type = QFileDialog.getSaveFileName(
            self,
            "Export Transactions",
            str(Path.home() / f"{self.current_account.name}.qif"),
            "QIF Files (*.qif);;CSV Files (*.csv);;All Files (*.*)",
        )

        if not file_path:
            return

        try:
            if file_path.endswith(".qif"):
                self.service.export_qif(file_path, self.current_account.id)
            elif file_path.endswith(".csv"):
                self.service.export_csv(file_path, self.current_account.id)
            else:
                QMessageBox.warning(self, "Unknown Format", "Please use .qif or .csv extension.")
                return

            QMessageBox.information(
                self, "Export Complete", f"Transactions exported to {file_path}"
            )
            self.statusBar().showMessage("Export complete")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error exporting file:\n{str(e)}")

    def manage_categories(self) -> None:
        """Open category management dialog."""
        dialog = CategoryDialog(self, self.service)
        dialog.exec()

    def manage_payees(self) -> None:
        """Open payee management dialog."""
        dialog = PayeeDialog(self, self.service)
        dialog.exec()

    def show_settings(self) -> None:
        """Open settings dialog."""
        dialog = SettingsDialog(self, self.settings)
        if dialog.exec() == QDialog.Accepted:  # type: ignore[attr-defined]
            self.settings.save()
            # Refresh display with new currency
            self.load_accounts(self.current_account.id if self.current_account else None)

    def show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            f"About {Config.APP_NAME}",
            f"{Config.APP_NAME} v{Config.APP_VERSION}\n\n"
            "A Microsoft Money 3.0 compatible personal finance application.\n\n"
            "Supports QIF, OFX, and CSV import/export.",
        )

    def closeEvent(self, event: Any) -> None:
        """Handle window close."""
        self.service.close()
        event.accept()

    def _update_window_title(self) -> None:
        """Update window title to show current database."""
        db_name = self.current_db_path.name
        db_dir = self.current_db_path.parent
        if db_dir == Config.get_user_data_dir():
            # Default location, just show filename
            self.setWindowTitle(f"{Config.APP_NAME} - {db_name}")
        else:
            # Custom location, show relative or full path
            try:
                rel_path = self.current_db_path.relative_to(Path.home())
                self.setWindowTitle(f"{Config.APP_NAME} - ~/{rel_path}")
            except ValueError:
                self.setWindowTitle(f"{Config.APP_NAME} - {self.current_db_path}")

    def _add_to_recent_databases(self, db_path: Path) -> None:
        """Add database to recent list."""
        recent = self.settings.get("recent_databases", [])
        if not isinstance(recent, list):
            recent = []

        db_str = str(db_path.resolve())
        if db_str in recent:
            recent.remove(db_str)
        recent.insert(0, db_str)
        recent = recent[:10]  # Keep only 10 most recent

        self.settings.set("recent_databases", recent)
        self.settings.save()

    def _update_recent_databases_menu(self) -> None:
        """Update the recent databases menu."""
        self.recent_menu.clear()
        recent = self.settings.get("recent_databases", [])

        if not recent:
            no_recent = QAction("(No recent databases)", self)
            no_recent.setEnabled(False)
            self.recent_menu.addAction(no_recent)
            return

        for db_path_str in recent:
            db_path = Path(db_path_str)
            if not db_path.exists():
                continue

            # Create display name
            if db_path.parent == Config.get_user_data_dir():
                display_name = db_path.name
            else:
                try:
                    rel_path = db_path.relative_to(Path.home())
                    display_name = f"~/{rel_path}"
                except ValueError:
                    display_name = str(db_path)

            action = QAction(display_name, self)
            action.setData(db_path_str)
            action.triggered.connect(
                lambda checked=False, p=db_path_str: self._open_database_path(Path(p))
            )
            self.recent_menu.addAction(action)

    def new_database(self) -> None:
        """Create a new database file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "New Database",
            str(Path.home() / "accounts.db"),
            "Database Files (*.db);;All Files (*.*)",
        )

        if not file_path:
            return

        db_path = Path(file_path)

        # Check if file exists
        if db_path.exists():
            reply = QMessageBox.question(
                self,
                "File Exists",
                f"Database file already exists. Open it instead?",
                QMessageBox.Yes | QMessageBox.No,  # type: ignore[attr-defined]
            )
            if reply == QMessageBox.Yes:  # type: ignore[attr-defined]
                self._open_database_path(db_path)
            return

        # Create new database by opening it
        self._open_database_path(db_path)
        self.statusBar().showMessage(f"Created new database: {db_path.name}")

    def open_database(self) -> None:
        """Open an existing database file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Database",
            str(Config.get_user_data_dir()),
            "Database Files (*.db);;All Files (*.*)",
        )

        if not file_path:
            return

        self._open_database_path(Path(file_path))

    def _open_database_path(self, db_path: Path) -> None:
        """Open a database at the given path."""
        if not db_path.exists():
            # Will be created by Storage
            pass

        # Close current service
        self.service.close()

        # Open new database
        self.current_db_path = db_path
        self.service = MoneyService(self.current_db_path)
        self.current_account = None

        # Reload UI
        self.load_accounts()
        self._add_to_recent_databases(db_path)
        self._update_recent_databases_menu()
        self._update_window_title()

        self.statusBar().showMessage(f"Opened database: {db_path.name}")


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
        self.balance_spin.setPrefix(settings.currency_symbol + " ")
        if self.account:
            self.balance_spin.setValue(float(self.account.opening_balance))
        layout.addRow("Opening Balance:", self.balance_spin)

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

        # Date
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("MM/dd/yyyy")
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

        # Add savings-specific transaction types
        if self.account.account_type == AccountType.SAVINGS:
            self.type_combo.addItem("Interest", "interest")
            if self.account.savings_subtype == SavingsAccountType.STOCKS_SHARES_ISA:
                self.type_combo.addItem("Dividend", "dividend")

        if self.transaction and self.transaction.amount >= 0:
            self.type_combo.setCurrentIndex(0)
        else:
            self.type_combo.setCurrentIndex(1)

        # Connect signal to update payee when type changes
        self.type_combo.currentIndexChanged.connect(self._on_transaction_type_changed)

        layout.addRow("Type:", self.type_combo)

        # Payee - editable combo box with predefined and historical payees
        self.payee_combo = QComboBox()
        self.payee_combo.setEditable(True)
        self.payee_combo.setInsertPolicy(QComboBox.NoInsert)  # type: ignore[attr-defined]

        # Load all payees (predefined + historical from transactions)
        all_payees = self.service.get_all_payees()
        self.payee_combo.addItems(all_payees)

        if self.transaction:
            self.payee_combo.setEditText(self.transaction.payee)

        layout.addRow("Payee:", self.payee_combo)

        # Amount
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 1000000)
        settings = get_settings()
        self.amount_spin.setDecimals(settings.decimal_places)
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

    def _on_transaction_type_changed(self) -> None:
        """Handle transaction type change to auto-populate fields."""
        trans_type = self.type_combo.currentData()

        # Auto-populate payee for interest and dividend types
        if trans_type == "interest":
            self.payee_combo.setEditText("Interest Payment")
        elif trans_type == "dividend":
            self.payee_combo.setEditText("Dividend Payment")
        elif trans_type == "deposit":
            # Clear auto-populated values for manual entry
            if self.payee_combo.currentText() in ["Interest Payment", "Dividend Payment"]:
                self.payee_combo.clearEditText()
        elif trans_type == "payment":
            # Clear auto-populated values for manual entry
            if self.payee_combo.currentText() in ["Interest Payment", "Dividend Payment"]:
                self.payee_combo.clearEditText()

    def get_data(self) -> dict[str, Any]:
        """Get dialog data."""
        qdate = self.date_edit.date()
        amount = Decimal(str(self.amount_spin.value()))
        trans_type = self.type_combo.currentData()

        # Payment types are negative, all others are positive
        if trans_type == "payment":
            amount = -amount

        return {
            "date": date(qdate.year(), qdate.month(), qdate.day()),
            "payee": self.payee_combo.currentText(),
            "amount": amount,
            "status": self.status_combo.currentData(),
            "memo": self.memo_edit.text(),
        }


class CategoryDialog(QDialog):
    """Dialog for managing categories."""

    def __init__(self, parent: Any, service: MoneyService) -> None:
        super().__init__(parent)
        self.service = service
        self.init_ui()
        self.load_categories()

    def init_ui(self) -> None:
        """Initialize dialog UI."""
        self.setWindowTitle("Categories")
        self.setModal(True)
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout()

        # Category list
        self.category_list = QListWidget()
        layout.addWidget(self.category_list)

        # Buttons
        btn_layout = QHBoxLayout()
        new_btn = QPushButton("New Category")
        new_btn.clicked.connect(self.new_category)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_category)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(new_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def load_categories(self) -> None:
        """Load categories into list."""
        self.category_list.clear()
        categories = self.service.get_all_categories()
        for cat in categories:
            income_indicator = "(Income)" if cat.is_income else "(Expense)"
            self.category_list.addItem(f"{cat.name} {income_indicator}")

    def new_category(self) -> None:
        """Create new category."""
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "New Category", "Category name:")
        if ok and name:
            self.service.create_category(name)
            self.load_categories()

    def delete_category(self) -> None:
        """Delete selected category."""
        row = self.category_list.currentRow()
        if row < 0:
            return

        categories = self.service.get_all_categories()
        if row < len(categories):
            category = categories[row]
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete category '{category.name}'?",
                QMessageBox.Yes | QMessageBox.No,  # type: ignore[attr-defined]
            )
            if reply == QMessageBox.Yes:  # type: ignore[attr-defined]
                self.service.delete_category(category.id)
                self.load_categories()


class PayeeDialog(QDialog):
    """Dialog for managing predefined payees."""

    def __init__(self, parent: Any, service: MoneyService) -> None:
        super().__init__(parent)
        self.service = service
        self.init_ui()
        self.load_payees()

    def init_ui(self) -> None:
        """Initialize dialog UI."""
        self.setWindowTitle("Manage Payees")
        self.setModal(True)
        self.setMinimumSize(500, 400)

        layout = QVBoxLayout()

        # Info label
        info_label = QLabel("Predefined payees appear in the dropdown when creating transactions.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Payee list
        self.payee_list = QListWidget()
        layout.addWidget(self.payee_list)

        # Buttons
        btn_layout = QHBoxLayout()
        new_btn = QPushButton("Add Payee")
        new_btn.clicked.connect(self.new_payee)
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_payee)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)

        btn_layout.addWidget(new_btn)
        btn_layout.addWidget(delete_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def load_payees(self) -> None:
        """Load predefined payees into list."""
        self.payee_list.clear()
        payees = self.service.get_predefined_payees()
        for payee in payees:
            self.payee_list.addItem(payee)

    def new_payee(self) -> None:
        """Add new predefined payee."""
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "Add Payee", "Payee name:")
        if ok and name and name.strip():
            self.service.add_payee(name.strip())
            self.load_payees()

    def delete_payee(self) -> None:
        """Delete selected predefined payee."""
        current_item = self.payee_list.currentItem()
        if not current_item:
            return

        payee_name = current_item.text()
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete payee '{payee_name}'?\n\nNote: This only removes it from the predefined list.\nExisting transactions will not be affected.",
            QMessageBox.Yes | QMessageBox.No,  # type: ignore[attr-defined]
        )
        if reply == QMessageBox.Yes:  # type: ignore[attr-defined]
            self.service.delete_payee(payee_name)
            self.load_payees()


class SettingsDialog(QDialog):
    """Dialog for application settings."""

    def __init__(self, parent: Any, settings: Any) -> None:
        super().__init__(parent)
        self.settings = settings
        self.init_ui()

    def init_ui(self) -> None:
        """Initialize dialog UI."""
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(450)

        layout = QVBoxLayout()
        form = QFormLayout()

        # Currency selection
        currency_label = QLabel("Currency:")
        self.currency_combo = QComboBox()

        # Add currencies sorted by code
        current_code = self.settings.currency_code
        current_index = 0
        for i, (code, info) in enumerate(sorted(CURRENCIES.items())):
            display_text = f"{code} - {info['name']} ({info['symbol']})"
            self.currency_combo.addItem(display_text, code)
            if code == current_code:
                current_index = i

        self.currency_combo.setCurrentIndex(current_index)
        form.addRow(currency_label, self.currency_combo)

        # Thousands separator
        self.thousands_check = QCheckBox("Use thousands separator (1,000.00)")
        self.thousands_check.setChecked(self.settings.get("thousands_separator", True))
        form.addRow("", self.thousands_check)

        # Date format
        date_label = QLabel("Date format:")
        self.date_combo = QComboBox()
        date_formats = [
            ("%m/%d/%Y", "MM/DD/YYYY (US)"),
            ("%d/%m/%Y", "DD/MM/YYYY (UK)"),
            ("%Y-%m-%d", "YYYY-MM-DD (ISO)"),
            ("%d.%m.%Y", "DD.MM.YYYY (DE)"),
        ]
        current_fmt = self.settings.date_format
        current_fmt_index = 0
        for i, (fmt, label) in enumerate(date_formats):
            self.date_combo.addItem(label, fmt)
            if fmt == current_fmt:
                current_fmt_index = i
        self.date_combo.setCurrentIndex(current_fmt_index)
        form.addRow(date_label, self.date_combo)

        layout.addLayout(form)

        # Preview
        layout.addSpacing(10)
        preview_group = QWidget()
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(10, 10, 10, 10)

        self.preview_label = QLabel()
        self.preview_label.setStyleSheet(
            "background-color: #f0f0f0; padding: 10px; border: 1px solid #ccc;"
        )
        self.update_preview()
        preview_layout.addWidget(QLabel("Preview:"))
        preview_layout.addWidget(self.preview_label)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)

        # Connect signals to update preview
        self.currency_combo.currentIndexChanged.connect(self.update_preview)
        self.thousands_check.stateChanged.connect(self.update_preview)
        self.date_combo.currentIndexChanged.connect(self.update_preview)

        # Buttons
        layout.addSpacing(10)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)  # type: ignore[attr-defined]
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def update_preview(self) -> None:
        """Update the preview label."""
        from datetime import date

        # Get current selections
        currency_code = self.currency_combo.currentData()
        use_thousands = self.thousands_check.isChecked()
        date_format = self.date_combo.currentData()

        # Create temporary settings for preview
        currency_info = CURRENCIES[currency_code]
        symbol = currency_info["symbol"]
        decimal_places = currency_info["decimal_places"]

        # Format sample amount
        amount = 1234.56
        if use_thousands:
            amount_str = f"{amount:,.{decimal_places}f}"
        else:
            amount_str = f"{amount:.{decimal_places}f}"

        if symbol in ["Fr", "kr", "R"]:
            currency_str = f"{symbol} {amount_str}"
        else:
            currency_str = f"{symbol}{amount_str}"

        # Format sample date
        sample_date = date(2026, 3, 15)
        date_str = sample_date.strftime(date_format)

        # Display preview
        preview_text = f"Amount: {currency_str}\nDate: {date_str}"
        self.preview_label.setText(preview_text)

    def accept(self) -> None:
        """Save settings and close."""
        # Save currency
        currency_code = self.currency_combo.currentData()
        self.settings.currency_code = currency_code

        # Save thousands separator
        self.settings.set("thousands_separator", self.thousands_check.isChecked())

        # Save date format
        date_format = self.date_combo.currentData()
        self.settings.date_format = date_format

        super().accept()


def QLineEdit_getText(parent: Any, title: str, label: str) -> tuple[str, bool]:
    """Simple helper for text input dialog."""
    from PySide6.QtWidgets import QInputDialog

    return QInputDialog.getText(parent, title, label)


# Monkey patch the helper
QLineEdit.getText = staticmethod(QLineEdit_getText)  # type: ignore[attr-defined]


# =============================================================================
# Investment Account UI
# =============================================================================


class InvestmentPanel(QWidget):
    """Right-panel shown when an investment account is selected.

    Layout: summary bar above a QTabWidget with Holdings and Transactions tabs.
    """

    HOLDINGS_COLUMNS = [
        "Security",
        "Ticker",
        "Type",
        "Shares",
        "Avg Cost",
        "Current Price",
        "Market Value",
        "Gain/Loss",
        "Gain/Loss %",
    ]
    TXN_COLUMNS = [
        "Date",
        "Security",
        "Type",
        "Shares",
        "Price",
        "Commission",
        "Amount",
        "Memo",
        "Status",
    ]

    def __init__(
        self,
        parent: Any,
        service: MoneyService,
        account: Account,
        settings: Any,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.account = account
        self.settings = settings
        self._init_ui()
        self.refresh()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # ---- Account header ----
        header_font = QFont()
        header_font.setBold(True)
        header_font.setPointSize(11)
        self.account_header = QLabel(f"{self.account.name} - Investment")
        self.account_header.setFont(header_font)
        layout.addWidget(self.account_header)

        # ---- Portfolio summary bar ----
        summary_box = QGroupBox("Portfolio Summary")
        summary_layout = QHBoxLayout(summary_box)
        self.lbl_cash = QLabel("Cash: —")
        self.lbl_holdings_val = QLabel("Holdings: —")
        self.lbl_total_val = QLabel("Total: —")
        self.lbl_ugl = QLabel("Unreal. G/L: —")
        self.lbl_xirr = QLabel("XIRR: —")
        for lbl in (
            self.lbl_cash,
            self.lbl_holdings_val,
            self.lbl_total_val,
            self.lbl_ugl,
            self.lbl_xirr,
        ):
            summary_layout.addWidget(lbl)
        layout.addWidget(summary_box)

        # ---- Tabs ----
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_holdings_tab(), "Holdings")
        self.tabs.addTab(self._create_transactions_tab(), "Transactions")
        layout.addWidget(self.tabs)

    def _create_holdings_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)

        # Toolbar
        btn_bar = QHBoxLayout()
        btn_buy = QPushButton("Buy")
        btn_sell = QPushButton("Sell")
        btn_price = QPushButton("Update Price")
        btn_fetch = QPushButton("Fetch Prices")
        btn_chart = QPushButton("View Chart")
        btn_manage = QPushButton("Manage Securities")
        for btn in (btn_buy, btn_sell, btn_price, btn_fetch, btn_chart, btn_manage):
            btn_bar.addWidget(btn)
        btn_bar.addStretch()
        vbox.addLayout(btn_bar)

        btn_buy.clicked.connect(self._on_buy)
        btn_sell.clicked.connect(self._on_sell)
        btn_price.clicked.connect(self._on_update_price)
        btn_fetch.clicked.connect(self._on_fetch_prices)
        btn_chart.clicked.connect(self._on_view_chart)
        btn_manage.clicked.connect(self._on_manage_securities)

        # Holdings table
        self.holdings_table = QTableWidget()
        self.holdings_table.setColumnCount(len(self.HOLDINGS_COLUMNS))
        self.holdings_table.setHorizontalHeaderLabels(self.HOLDINGS_COLUMNS)
        self.holdings_table.setSelectionBehavior(
            QTableWidget.SelectRows  # type: ignore[attr-defined]
        )
        self.holdings_table.setEditTriggers(
            QTableWidget.NoEditTriggers  # type: ignore[attr-defined]
        )
        self.holdings_table.horizontalHeader().setStretchLastSection(True)
        vbox.addWidget(self.holdings_table)
        return tab

    def _create_transactions_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)

        btn_bar = QHBoxLayout()
        btn_new = QPushButton("New")
        btn_edit = QPushButton("Edit")
        btn_delete = QPushButton("Delete")
        for btn in (btn_new, btn_edit, btn_delete):
            btn_bar.addWidget(btn)
        btn_bar.addStretch()
        vbox.addLayout(btn_bar)

        btn_new.clicked.connect(self._on_new_txn)
        btn_edit.clicked.connect(self._on_edit_txn)
        btn_delete.clicked.connect(self._on_delete_txn)

        self.txn_table = QTableWidget()
        self.txn_table.setColumnCount(len(self.TXN_COLUMNS))
        self.txn_table.setHorizontalHeaderLabels(self.TXN_COLUMNS)
        self.txn_table.setSelectionBehavior(QTableWidget.SelectRows)  # type: ignore[attr-defined]
        self.txn_table.setEditTriggers(QTableWidget.NoEditTriggers)  # type: ignore[attr-defined]
        self.txn_table.horizontalHeader().setStretchLastSection(True)
        self.txn_table.doubleClicked.connect(self._on_edit_txn)
        vbox.addWidget(self.txn_table)
        return tab

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Reload all data from service."""
        # Re-fetch account to get latest balance
        latest = self.service.get_account(self.account.id)
        if latest:
            self.account = latest
        self.load_holdings()
        self.load_investment_transactions()
        self.update_summary()

    def load_holdings(self) -> None:
        holdings = self.service.get_holdings_for_account(self.account.id)
        self.holdings_table.setRowCount(len(holdings))
        for row, h in enumerate(holdings):

            def _cell(val: str, align: Qt.AlignmentFlag = Qt.AlignLeft) -> QTableWidgetItem:  # type: ignore[attr-defined]
                item = QTableWidgetItem(val)
                item.setTextAlignment(int(align) | int(Qt.AlignVCenter))  # type: ignore[attr-defined]
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # type: ignore[attr-defined]
                return item

            right = Qt.AlignRight  # type: ignore[attr-defined]
            self.holdings_table.setItem(row, 0, _cell(h.security.name))
            self.holdings_table.setItem(row, 1, _cell(h.security.ticker_symbol))
            self.holdings_table.setItem(row, 2, _cell(h.security.security_type.value))
            self.holdings_table.setItem(
                row, 3, _cell(f"{h.shares:,.4f}".rstrip("0").rstrip("."), right)
            )
            self.holdings_table.setItem(
                row, 4, _cell(self.settings.format_currency(h.avg_cost), right)
            )
            if h.current_price is not None:
                self.holdings_table.setItem(
                    row, 5, _cell(self.settings.format_currency(h.current_price), right)
                )
                self.holdings_table.setItem(
                    row, 6, _cell(self.settings.format_currency(h.market_value), right)
                )
            else:
                self.holdings_table.setItem(row, 5, _cell("—", right))
                self.holdings_table.setItem(row, 6, _cell("—", right))
            if h.gain_loss is not None and h.gain_loss_pct is not None:
                gl_item = _cell(self.settings.format_currency(h.gain_loss), right)
                pct_item = _cell(f"{h.gain_loss_pct:.2f}%", right)
                color = QColor("#006400") if h.gain_loss >= Decimal("0") else QColor("#8B0000")
                gl_item.setForeground(color)
                pct_item.setForeground(color)
                self.holdings_table.setItem(row, 7, gl_item)
                self.holdings_table.setItem(row, 8, pct_item)
            else:
                self.holdings_table.setItem(row, 7, _cell("—", right))
                self.holdings_table.setItem(row, 8, _cell("—", right))

        self.holdings_table.resizeColumnsToContents()

    def load_investment_transactions(self) -> None:
        txns = self.service.get_investment_transactions_for_account(self.account.id)
        securities = {s.id: s for s in self.service.get_all_securities()}
        self.txn_table.setRowCount(len(txns))
        for row, txn in enumerate(txns):
            sec_name = securities[txn.security_id].name if txn.security_id else "—"
            items = [
                txn.date.strftime(self.settings.date_format),
                sec_name,
                txn.transaction_type.value,
                (f"{txn.quantity:,.4f}".rstrip("0").rstrip(".") if txn.quantity else "—"),
                (self.settings.format_currency(txn.price) if txn.price else "—"),
                (self.settings.format_currency(txn.commission) if txn.commission else "—"),
                self.settings.format_currency(txn.amount),
                txn.memo,
                txn.status.value,
            ]
            for col, text in enumerate(items):
                item = QTableWidgetItem(text)
                item.setData(Qt.UserRole, txn.id)  # type: ignore[attr-defined]
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # type: ignore[attr-defined]
                self.txn_table.setItem(row, col, item)
        self.txn_table.resizeColumnsToContents()

    def update_summary(self) -> None:
        summary = self.service.get_portfolio_summary(self.account.id)
        fmt = self.settings.format_currency

        self.lbl_cash.setText(f"Cash: {fmt(summary.cash_balance)}")
        self.lbl_holdings_val.setText(
            f"Holdings: {fmt(summary.holdings_value) if summary.holdings_value is not None else '—'}"
        )
        self.lbl_total_val.setText(
            f"Total: {fmt(summary.total_value) if summary.total_value is not None else '—'}"
        )
        if summary.unrealized_gain_loss is not None:
            ugl = summary.unrealized_gain_loss
            color = "green" if ugl >= Decimal("0") else "red"
            self.lbl_ugl.setText(f"<span style='color:{color}'>Unreal. G/L: {fmt(ugl)}</span>")
        else:
            self.lbl_ugl.setText("Unreal. G/L: —")
        self.lbl_ugl.setTextFormat(Qt.RichText)  # type: ignore[attr-defined]

        if summary.roi_xirr is not None:
            xirr_pct = float(summary.roi_xirr) * 100
            color = "green" if xirr_pct >= 0 else "red"
            self.lbl_xirr.setText(f"<span style='color:{color}'>XIRR: {xirr_pct:.2f}%</span>")
        else:
            self.lbl_xirr.setText("XIRR: —")
        self.lbl_xirr.setTextFormat(Qt.RichText)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Holdings toolbar actions
    # ------------------------------------------------------------------

    def _on_buy(self) -> None:
        self._open_txn_dialog(preset_type=InvestmentTransactionType.BUY)

    def _on_sell(self) -> None:
        self._open_txn_dialog(preset_type=InvestmentTransactionType.SELL)

    def _open_txn_dialog(
        self,
        txn: Optional[InvestmentTransaction] = None,
        preset_type: Optional[InvestmentTransactionType] = None,
    ) -> None:
        dialog = InvestmentTransactionDialog(self, self.service, self.account, txn, preset_type)
        if dialog.exec() == QDialog.Accepted:  # type: ignore[attr-defined]
            data = dialog.get_data()
            if txn is None:
                self.service.create_investment_transaction(**data)
            else:
                for k, v in data.items():
                    setattr(txn, k, v)
                self.service.update_investment_transaction(txn)
            self.refresh()

    def _on_update_price(self) -> None:
        row = self.holdings_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No Selection", "Select a holding first.")
            return
        name_item = self.holdings_table.item(row, 0)
        if name_item is None:
            return
        sec_name = name_item.text()
        security = next((s for s in self.service.get_all_securities() if s.name == sec_name), None)
        if security is None:
            return
        dialog = UpdatePriceDialog(self, security)
        if dialog.exec() == QDialog.Accepted:  # type: ignore[attr-defined]
            price_date, price = dialog.get_data()
            self.service.add_security_price(security.id, price_date, price, source="manual")
            self.refresh()

    def _on_fetch_prices(self) -> None:
        securities = self.service.get_all_securities()
        tickers = [(s.id, s.ticker_symbol) for s in securities if s.ticker_symbol]
        if not tickers:
            QMessageBox.information(
                self,
                "No Tickers",
                "No securities have ticker symbols set.\n" "Edit a security to add a ticker.",
            )
            return
        self._fetch_worker = PriceFetchWorker(tickers, self.service)
        self._fetch_worker.finished.connect(self._on_fetch_done)
        self._fetch_worker.error.connect(self._on_fetch_error)
        self._fetch_worker.start()
        self.statusBar_message("Fetching prices…")

    def statusBar_message(self, msg: str) -> None:  # noqa: N802
        win = self.window()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage(msg)

    def _on_fetch_done(self, updated: int) -> None:
        self.statusBar_message(f"Fetched prices for {updated} securities.")
        self.refresh()

    def _on_fetch_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Price Fetch Error", msg)

    def _on_view_chart(self) -> None:
        row = self.holdings_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No Selection", "Select a holding to view chart.")
            return
        name_item = self.holdings_table.item(row, 0)
        if name_item is None:
            return
        sec_name = name_item.text()
        security = next((s for s in self.service.get_all_securities() if s.name == sec_name), None)
        if security is None:
            return
        history = self.service.get_price_history(security.id)
        if len(history) < 2:
            QMessageBox.information(
                self, "Not Enough Data", "Need at least 2 price records to show a chart."
            )
            return
        dialog = PriceHistoryDialog(self, security, history, self.settings)
        dialog.exec()

    def _on_manage_securities(self) -> None:
        dialog = ManageSecuritiesDialog(self, self.service)
        dialog.exec()
        self.refresh()

    # ------------------------------------------------------------------
    # Transactions toolbar actions
    # ------------------------------------------------------------------

    def _on_new_txn(self) -> None:
        self._open_txn_dialog()

    def _on_edit_txn(self) -> None:
        row = self.txn_table.currentRow()
        if row < 0:
            return
        item = self.txn_table.item(row, 0)
        if not item:
            return
        txn_id = item.data(Qt.UserRole)  # type: ignore[attr-defined]
        txn = self.service.get_investment_transaction(txn_id)
        if txn:
            self._open_txn_dialog(txn=txn)

    def _on_delete_txn(self) -> None:
        row = self.txn_table.currentRow()
        if row < 0:
            return
        item = self.txn_table.item(row, 0)
        if not item:
            return
        txn_id = item.data(Qt.UserRole)  # type: ignore[attr-defined]
        reply = QMessageBox.question(
            self,
            "Delete Transaction",
            "Delete this investment transaction?",
            QMessageBox.Yes | QMessageBox.No,  # type: ignore[attr-defined]
        )
        if reply == QMessageBox.Yes:  # type: ignore[attr-defined]
            self.service.delete_investment_transaction(txn_id, self.account.id)
            self.refresh()


# =============================================================================
# Investment Transaction Dialog
# =============================================================================

# Types where quantity + price fields make sense
_NEEDS_QTY = frozenset(
    [
        InvestmentTransactionType.BUY,
        InvestmentTransactionType.SELL,
        InvestmentTransactionType.ADD,
        InvestmentTransactionType.REMOVE,
        InvestmentTransactionType.REINV_DIV,
    ]
)

# Types where commission makes sense
_NEEDS_COMMISSION = frozenset(
    [
        InvestmentTransactionType.BUY,
        InvestmentTransactionType.SELL,
    ]
)


class InvestmentTransactionDialog(QDialog):
    """Dialog for creating / editing an investment transaction."""

    def __init__(
        self,
        parent: Any,
        service: MoneyService,
        account: Account,
        txn: Optional[InvestmentTransaction] = None,
        preset_type: Optional[InvestmentTransactionType] = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.account = account
        self.txn = txn
        self.preset_type = preset_type
        self.setWindowTitle("Edit Investment Transaction" if txn else "New Investment Transaction")
        self.setModal(True)
        self.setMinimumWidth(420)
        self._init_ui()
        if txn:
            self._populate(txn)
        elif preset_type:
            idx = self.type_combo.findData(preset_type)
            if idx >= 0:
                self.type_combo.setCurrentIndex(idx)

    def _init_ui(self) -> None:
        layout = QFormLayout(self)

        settings = get_settings()

        # Date
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        layout.addRow("Date:", self.date_edit)

        # Transaction type
        self.type_combo = QComboBox()
        for t in InvestmentTransactionType:
            self.type_combo.addItem(t.value, t)
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        layout.addRow("Type:", self.type_combo)

        # Security
        self.security_combo = QComboBox()
        self.security_combo.addItem("— Cash only —", None)
        for sec in self.service.get_all_securities():
            self.security_combo.addItem(f"{sec.name} ({sec.ticker_symbol})", sec.id)
        layout.addRow("Security:", self.security_combo)

        # Quantity
        self.qty_label = QLabel("Quantity:")
        self.qty_spin = QDoubleSpinBox()
        self.qty_spin.setDecimals(4)
        self.qty_spin.setRange(0, 1_000_000_000)
        self.qty_spin.setGroupSeparatorShown(True)
        layout.addRow(self.qty_label, self.qty_spin)

        # Price per share
        self.price_label = QLabel("Price per Share:")
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setDecimals(settings.decimal_places)
        self.price_spin.setRange(0, 1_000_000_000)
        self.price_spin.setGroupSeparatorShown(True)
        self.price_spin.setPrefix(settings.currency_symbol + " ")
        layout.addRow(self.price_label, self.price_spin)

        # Commission
        self.commission_label = QLabel("Commission:")
        self.commission_spin = QDoubleSpinBox()
        self.commission_spin.setDecimals(settings.decimal_places)
        self.commission_spin.setRange(0, 1_000_000)
        self.commission_spin.setPrefix(settings.currency_symbol + " ")
        layout.addRow(self.commission_label, self.commission_spin)

        # Cash amount override for income-type entries
        self.amount_label = QLabel("Amount:")
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setDecimals(settings.decimal_places)
        self.amount_spin.setRange(0, 1_000_000_000)
        self.amount_spin.setPrefix(settings.currency_symbol + " ")
        layout.addRow(self.amount_label, self.amount_spin)

        # Memo
        self.memo_edit = QLineEdit()
        layout.addRow("Memo:", self.memo_edit)

        # Status
        self.status_combo = QComboBox()
        self.status_combo.addItem("Uncleared", TransactionStatus.UNCLEARED)
        self.status_combo.addItem("Cleared", TransactionStatus.CLEARED)
        self.status_combo.addItem("Reconciled", TransactionStatus.RECONCILED)
        layout.addRow("Status:", self.status_combo)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel  # type: ignore[attr-defined]
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._on_type_changed()

    def _on_type_changed(self) -> None:
        txn_type: InvestmentTransactionType = self.type_combo.currentData()
        needs_qty = txn_type in _NEEDS_QTY
        needs_commission = txn_type in _NEEDS_COMMISSION
        # Income types use the amount_spin instead of qty+price
        is_income = txn_type not in _NEEDS_QTY

        for w in (self.qty_label, self.qty_spin, self.price_label, self.price_spin):
            w.setVisible(needs_qty)
        for w in (self.commission_label, self.commission_spin):
            w.setVisible(needs_commission)
        for w in (self.amount_label, self.amount_spin):
            w.setVisible(is_income)

    def _populate(self, txn: InvestmentTransaction) -> None:
        d = txn.date
        self.date_edit.setDate(QDate(d.year, d.month, d.day))

        idx = self.type_combo.findData(txn.transaction_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        if txn.security_id:
            sec_idx = self.security_combo.findData(txn.security_id)
            if sec_idx >= 0:
                self.security_combo.setCurrentIndex(sec_idx)

        self.qty_spin.setValue(float(txn.quantity))
        self.price_spin.setValue(float(txn.price))
        self.commission_spin.setValue(float(txn.commission))
        self.amount_spin.setValue(abs(float(txn.amount)))
        self.memo_edit.setText(txn.memo)

        idx = self.status_combo.findData(txn.status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)

    def get_data(self) -> Dict[str, Any]:
        """Return data suitable for create_investment_transaction / update."""
        qd = self.date_edit.date()
        txn_type: InvestmentTransactionType = self.type_combo.currentData()

        if txn_type in _NEEDS_QTY:
            qty = Decimal(str(self.qty_spin.value()))
            price = Decimal(str(self.price_spin.value()))
            commission = Decimal(str(self.commission_spin.value()))
        else:
            qty = Decimal("0")
            price = Decimal(str(self.amount_spin.value()))
            commission = Decimal("0")

        return {
            "account_id": self.account.id,
            "transaction_type": txn_type,
            "txn_date": date(qd.year(), qd.month(), qd.day()),
            "security_id": self.security_combo.currentData(),
            "quantity": qty,
            "price": price,
            "commission": commission,
            "memo": self.memo_edit.text(),
            "status": self.status_combo.currentData(),
        }


# =============================================================================
# Security Dialogs
# =============================================================================


class SecurityDialog(QDialog):
    """Dialog for creating / editing a security."""

    def __init__(self, parent: Any, security: Optional[Security] = None) -> None:
        super().__init__(parent)
        self.security = security
        self.setWindowTitle("Edit Security" if security else "New Security")
        self.setModal(True)
        self.setMinimumWidth(380)
        self._init_ui()
        if security:
            self._populate(security)

    def _init_ui(self) -> None:
        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        layout.addRow("Name:", self.name_edit)

        self.ticker_edit = QLineEdit()
        self.ticker_edit.setPlaceholderText("e.g. AAPL (optional)")
        layout.addRow("Ticker Symbol:", self.ticker_edit)

        self.type_combo = QComboBox()
        for st in SecurityType:
            self.type_combo.addItem(st.value, st)
        layout.addRow("Type:", self.type_combo)

        self.notes_edit = QLineEdit()
        layout.addRow("Notes:", self.notes_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel  # type: ignore[attr-defined]
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _populate(self, sec: Security) -> None:
        self.name_edit.setText(sec.name)
        self.ticker_edit.setText(sec.ticker_symbol)
        idx = self.type_combo.findData(sec.security_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        self.notes_edit.setText(sec.notes)

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Security name is required.")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "name": self.name_edit.text().strip(),
            "ticker_symbol": self.ticker_edit.text().strip().upper(),
            "security_type": self.type_combo.currentData(),
            "notes": self.notes_edit.text().strip(),
        }


class ManageSecuritiesDialog(QDialog):
    """Dialog for listing, creating, and deleting securities."""

    def __init__(self, parent: Any, service: MoneyService) -> None:
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Manage Securities")
        self.setModal(True)
        self.setMinimumSize(480, 360)
        self._init_ui()
        self._load()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_bar = QHBoxLayout()
        btn_new = QPushButton("New")
        btn_edit = QPushButton("Edit")
        btn_delete = QPushButton("Delete")
        btn_close = QPushButton("Close")
        for b in (btn_new, btn_edit, btn_delete, btn_close):
            btn_bar.addWidget(b)
        layout.addLayout(btn_bar)

        btn_new.clicked.connect(self._on_new)
        btn_edit.clicked.connect(self._on_edit)
        btn_delete.clicked.connect(self._on_delete)
        btn_close.clicked.connect(self.accept)

    def _load(self) -> None:
        self.list_widget.clear()
        for sec in self.service.get_all_securities():
            from PySide6.QtWidgets import QListWidgetItem

            item = QListWidgetItem(
                f"{sec.name}  [{sec.ticker_symbol or '—'}]  {sec.security_type.value}"
            )
            item.setData(Qt.UserRole, sec.id)  # type: ignore[attr-defined]
            self.list_widget.addItem(item)

    def _on_new(self) -> None:
        dialog = SecurityDialog(self)
        if dialog.exec() == QDialog.Accepted:  # type: ignore[attr-defined]
            d = dialog.get_data()
            self.service.create_security(**d)
            self._load()

    def _on_edit(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            return
        sec_id = item.data(Qt.UserRole)  # type: ignore[attr-defined]
        sec = self.service.get_security(sec_id)
        if not sec:
            return
        dialog = SecurityDialog(self, sec)
        if dialog.exec() == QDialog.Accepted:  # type: ignore[attr-defined]
            d = dialog.get_data()
            sec.name = d["name"]
            sec.ticker_symbol = d["ticker_symbol"]
            sec.security_type = d["security_type"]
            sec.notes = d["notes"]
            self.service.update_security(sec)
            self._load()

    def _on_delete(self) -> None:
        item = self.list_widget.currentItem()
        if not item:
            return
        reply = QMessageBox.question(
            self,
            "Delete Security",
            f"Delete '{item.text()}'?\n\nThis also removes all price history.",
            QMessageBox.Yes | QMessageBox.No,  # type: ignore[attr-defined]
        )
        if reply == QMessageBox.Yes:  # type: ignore[attr-defined]
            sec_id = item.data(Qt.UserRole)  # type: ignore[attr-defined]
            self.service.delete_security(sec_id)
            self._load()


# =============================================================================
# Update Price Dialog
# =============================================================================


class UpdatePriceDialog(QDialog):
    def __init__(self, parent: Any, security: Security) -> None:
        super().__init__(parent)
        self.security = security
        self.setWindowTitle(f"Update Price — {security.name}")
        self.setModal(True)
        self.setMinimumWidth(320)
        self._init_ui()

    def _init_ui(self) -> None:
        settings = get_settings()
        layout = QFormLayout(self)

        layout.addRow(QLabel(f"Security: <b>{self.security.name}</b>"))

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        layout.addRow("Date:", self.date_edit)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setDecimals(settings.decimal_places)
        self.price_spin.setRange(0, 1_000_000_000)
        self.price_spin.setPrefix(settings.currency_symbol + " ")
        layout.addRow("Price:", self.price_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel  # type: ignore[attr-defined]
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_data(self) -> tuple[date, Decimal]:
        qd = self.date_edit.date()
        price_date = date(qd.year(), qd.month(), qd.day())
        return price_date, Decimal(str(self.price_spin.value()))


# =============================================================================
# Price History Chart Dialog
# =============================================================================


class PriceHistoryDialog(QDialog):
    """Shows a line chart of a security's price history using PySide6.QtCharts."""

    def __init__(
        self,
        parent: Any,
        security: Security,
        history: List[SecurityPrice],
        settings: Any,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Price History — {security.name}")
        self.setModal(True)
        self.resize(700, 450)
        self._build(security, history, settings)

    def _build(self, security: Security, history: List[SecurityPrice], settings: Any) -> None:
        layout = QVBoxLayout(self)
        try:
            from PySide6.QtCharts import QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis
            from PySide6.QtCore import QDateTime

            series = QLineSeries()
            series.setName(security.name)
            for sp in history:
                dt = QDateTime(
                    QDate(sp.date.year, sp.date.month, sp.date.day),
                    QTime(0, 0, 0),
                )
                series.append(dt.toMSecsSinceEpoch(), float(sp.price))

            chart = QChart()
            chart.addSeries(series)
            chart.setTitle(f"{security.name} Price History")

            x_axis = QDateTimeAxis()
            x_axis.setFormat("dd MMM yy")
            x_axis.setTitleText("Date")
            chart.addAxis(x_axis, Qt.AlignBottom)  # type: ignore[attr-defined]
            series.attachAxis(x_axis)

            y_axis = QValueAxis()
            y_axis.setTitleText(f"Price ({settings.currency_symbol})")
            chart.addAxis(y_axis, Qt.AlignLeft)  # type: ignore[attr-defined]
            series.attachAxis(y_axis)

            view = QChartView(chart)
            view.setRenderHint(view.renderHints().__class__.Antialiasing)
            layout.addWidget(view)
        except ImportError:
            layout.addWidget(
                QLabel(
                    "PySide6.QtCharts is not available.\n"
                    "Install the PySide6-Addons package to enable charts."
                )
            )

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


# =============================================================================
# Price Fetch Worker (background thread)
# =============================================================================


class PriceFetchWorker(QThread):
    """Fetches prices from yfinance in a background thread."""

    finished = Signal(int)  # number of securities updated
    error = Signal(str)  # error message if yfinance unavailable

    def __init__(self, tickers: List[tuple[str, str]], service: MoneyService) -> None:
        super().__init__()
        self.tickers = tickers  # list of (security_id, ticker_symbol)
        self.service = service

    def run(self) -> None:
        updated = 0
        for security_id, ticker in self.tickers:
            try:
                price = self.service.fetch_price_from_api(ticker)
            except ImportError as exc:
                self.error.emit(str(exc))
                return
            if price is not None:
                from datetime import date as _date

                self.service.add_security_price(security_id, _date.today(), price, source="api")
                updated += 1
        self.finished.emit(updated)
