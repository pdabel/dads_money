"""Main application window."""

from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..config import Config
from ..models import Account, AccountType, Transaction, TransactionStatus
from ..services import MoneyService
from ..settings import get_settings
from .account_dialogs import AccountDialog, TransactionDialog
from .investment_panel import InvestmentPanel
from .manage_dialogs import CategoryDialog, PayeeDialog
from .settings_dialog import SettingsDialog


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
