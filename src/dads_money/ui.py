"""Microsoft Money 3.0-style desktop UI."""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QSplitter, QDialog, QLineEdit, QComboBox, QDateEdit, QTextEdit,
    QFileDialog, QMessageBox, QHeaderView, QDialogButtonBox, QFormLayout,
    QDoubleSpinBox, QCheckBox
)

from .config import Config
from .models import Account, AccountType, Transaction, TransactionStatus, Category
from .services import MoneyService
from .settings import get_settings, CURRENCIES


class MainWindow(QMainWindow):
    """Main application window with Money 3.0 style interface."""
    REGISTER_COLUMNS = ["Date", "Check #", "Payee", "Memo", "Status", "Credit", "Debit", "Balance"]
    
    def __init__(self):
        super().__init__()
        self.service = MoneyService()
        self.settings = get_settings()
        self.current_account: Optional[Account] = None
        self.init_ui()
        self.load_accounts()
    
    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(f"{Config.APP_NAME} - Microsoft Money 3.0 Style")
        self.setGeometry(100, 100, 1200, 700)
        
        # Create menu bar
        self.create_menus()
        
        # Create toolbar
        self.create_toolbar()
        
        # Create main widget with splitter
        central = QWidget()
        main_layout = QHBoxLayout()
        
        # Create splitter for accounts and register
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Account list
        left_panel = self.create_account_panel()
        splitter.addWidget(left_panel)
        
        # Right panel - Register
        right_panel = self.create_register_panel()
        splitter.addWidget(right_panel)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(splitter)
        central.setLayout(main_layout)
        self.setCentralWidget(central)
        
        # Status bar
        self.statusBar().showMessage("Ready")
    
    def create_menus(self):
        """Create menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
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
    
    def create_toolbar(self):
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
        self.transaction_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.transaction_table.setSelectionBehavior(QTableWidget.SelectRows)
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

    def apply_register_column_visibility(self):
        """Apply register column visibility from user settings."""
        default_visible = list(range(len(self.REGISTER_COLUMNS)))
        stored_visible = self.settings.get("register_visible_columns", default_visible)

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
            self.transaction_table.setColumnHidden(column_index, column_index not in visible_columns)

    def choose_register_columns(self):
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

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        reset_button = buttons.addButton("Reset to Default", QDialogButtonBox.ResetRole)

        def save_columns():
            visible_columns = [
                index for index, checkbox in enumerate(checkboxes)
                if checkbox.isChecked()
            ]

            if not visible_columns:
                QMessageBox.warning(dialog, "No Columns Selected", "Please select at least one column.")
                return

            self.settings.set("register_visible_columns", visible_columns)
            self.settings.save()
            self.apply_register_column_visibility()
            dialog.accept()

        def reset_columns():
            for checkbox in checkboxes:
                checkbox.setChecked(True)
            default_visible = list(range(len(self.REGISTER_COLUMNS)))
            self.settings.set("register_visible_columns", default_visible)
            self.settings.save()
            self.apply_register_column_visibility()

        buttons.accepted.connect(save_columns)
        buttons.rejected.connect(dialog.reject)
        reset_button.clicked.connect(reset_columns)
        layout.addWidget(buttons)

        dialog.setLayout(layout)
        dialog.exec()
    
    def load_accounts(self, selected_account_id: Optional[str] = None):
        """Load accounts into the list."""
        if selected_account_id is None and self.current_account:
            selected_account_id = self.current_account.id

        self.account_list.clear()
        accounts = self.service.get_all_accounts()
        selected_index = -1

        for index, account in enumerate(accounts):
            balance_str = self.settings.format_currency(account.current_balance)
            item = QListWidgetItem(f"{account.name} - {balance_str}")
            item.setData(Qt.UserRole, account.id)
            self.account_list.addItem(item)
            if account.id == selected_account_id:
                selected_index = index
        
        if accounts:
            self.account_list.setCurrentRow(selected_index if selected_index >= 0 else 0)
        else:
            self.current_account = None
    
    def account_selected(self, index):
        """Handle account selection."""
        if index < 0:
            return

        selected_item = self.account_list.item(index)
        if not selected_item:
            return

        account_id = selected_item.data(Qt.UserRole)
        if not account_id:
            return

        account = self.service.get_account(account_id)
        if not account:
            return

        self.current_account = account
        self.load_transactions()
    
    def load_transactions(self):
        """Load transactions for current account."""
        if not self.current_account:
            return
        
        self.account_header.setText(
            f"{self.current_account.name} - {self.current_account.account_type.value}"
        )
        balance_formatted = self.settings.format_currency(self.current_account.current_balance)
        self.balance_label.setText(
            f"Current Balance: {balance_formatted}"
        )
        
        transactions = self.service.get_transactions_for_account(self.current_account.id)
        transactions = sorted(transactions, key=lambda t: (t.date, t.created_date))
        running_balance = self.current_account.opening_balance
        
        self.transaction_table.setRowCount(len(transactions) + 1)

        opening_date = self.current_account.created_date.strftime(self.settings.date_format)
        self.transaction_table.setItem(0, 0, QTableWidgetItem(opening_date))
        self.transaction_table.setItem(0, 1, QTableWidgetItem(""))
        self.transaction_table.setItem(0, 2, QTableWidgetItem("Opening Balance"))
        self.transaction_table.setItem(0, 3, QTableWidgetItem(""))
        self.transaction_table.setItem(0, 4, QTableWidgetItem(""))
        self.transaction_table.setItem(0, 5, QTableWidgetItem(""))
        self.transaction_table.setItem(0, 6, QTableWidgetItem(""))
        opening_balance_item = QTableWidgetItem(self.settings.format_currency(running_balance))
        opening_balance_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.transaction_table.setItem(0, 7, opening_balance_item)

        for i, trans in enumerate(transactions, start=1):
            date_formatted = trans.date.strftime(self.settings.date_format)
            self.transaction_table.setItem(i, 0, QTableWidgetItem(date_formatted))
            self.transaction_table.setItem(i, 1, QTableWidgetItem(trans.check_number))
            self.transaction_table.setItem(i, 2, QTableWidgetItem(trans.payee))
            self.transaction_table.setItem(i, 3, QTableWidgetItem(trans.memo))
            
            status_text = ""
            if trans.status == TransactionStatus.RECONCILED:
                status_text = "R"
            elif trans.status == TransactionStatus.CLEARED:
                status_text = "C"
            self.transaction_table.setItem(i, 4, QTableWidgetItem(status_text))

            credit_text = ""
            debit_text = ""
            if trans.amount >= 0:
                credit_text = self.settings.format_currency(trans.amount)
            else:
                debit_text = self.settings.format_currency(abs(trans.amount))

            credit_item = QTableWidgetItem(credit_text)
            credit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.transaction_table.setItem(i, 5, credit_item)

            debit_item = QTableWidgetItem(debit_text)
            debit_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.transaction_table.setItem(i, 6, debit_item)

            running_balance += trans.amount
            balance_formatted = self.settings.format_currency(running_balance)
            balance_item = QTableWidgetItem(balance_formatted)
            balance_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.transaction_table.setItem(i, 7, balance_item)
            
            # Store transaction ID in first column for reference
            self.transaction_table.item(i, 0).setData(Qt.UserRole, trans.id)
    
    def new_account(self):
        """Create a new account."""
        dialog = AccountDialog(self)
        if dialog.exec() == QDialog.Accepted:
            account_data = dialog.get_data()
            account = self.service.create_account(
                name=account_data['name'],
                account_type=account_data['type'],
                opening_balance=account_data['opening_balance']
            )
            self.load_accounts(account.id)
            self.statusBar().showMessage(f"Account '{account_data['name']}' created")
    
    def edit_account(self):
        """Edit the selected account."""
        if not self.current_account:
            QMessageBox.warning(self, "No Account", "Please select an account to edit.")
            return
        
        dialog = AccountDialog(self, self.current_account)
        if dialog.exec() == QDialog.Accepted:
            account_data = dialog.get_data()
            self.current_account.name = account_data['name']
            self.current_account.account_type = account_data['type']
            self.current_account.opening_balance = account_data['opening_balance']
            self.service.update_account(self.current_account)
            self.load_accounts(self.current_account.id)
            self.statusBar().showMessage(f"Account '{account_data['name']}' updated")
    
    def new_transaction(self):
        """Create a new transaction."""
        if not self.current_account:
            QMessageBox.warning(self, "No Account", "Please select an account first.")
            return
        
        dialog = TransactionDialog(self, self.service, self.current_account)
        if dialog.exec() == QDialog.Accepted:
            trans_data = dialog.get_data()
            trans = Transaction(
                account_id=self.current_account.id,
                date=trans_data['date'],
                payee=trans_data['payee'],
                memo=trans_data['memo'],
                amount=trans_data['amount'],
                check_number=trans_data['check_number'],
                status=trans_data['status']
            )
            self.service.update_transaction(trans)
            self.load_accounts(self.current_account.id)  # Refresh balance and keep selection
            self.statusBar().showMessage("Transaction created")
    
    def edit_transaction(self):
        """Edit the selected transaction."""
        row = self.transaction_table.currentRow()
        if row < 0:
            return
        
        trans_id = self.transaction_table.item(row, 0).data(Qt.UserRole)
        transaction = self.service.get_transaction(trans_id)
        
        if transaction:
            dialog = TransactionDialog(self, self.service, self.current_account, transaction)
            if dialog.exec() == QDialog.Accepted:
                trans_data = dialog.get_data()
                transaction.date = trans_data['date']
                transaction.payee = trans_data['payee']
                transaction.memo = trans_data['memo']
                transaction.amount = trans_data['amount']
                transaction.check_number = trans_data['check_number']
                transaction.status = trans_data['status']
                self.service.update_transaction(transaction)
                self.load_accounts(self.current_account.id)
                self.statusBar().showMessage("Transaction updated")
    
    def delete_transaction(self):
        """Delete the selected transaction."""
        row = self.transaction_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a transaction to delete.")
            return
        
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Are you sure you want to delete this transaction?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            trans_id = self.transaction_table.item(row, 0).data(Qt.UserRole)
            self.service.delete_transaction(trans_id, self.current_account.id)
            self.load_accounts(self.current_account.id)
            self.statusBar().showMessage("Transaction deleted")
    
    def import_transactions(self):
        """Import transactions from file."""
        if not self.current_account:
            QMessageBox.warning(self, "No Account", "Please select an account first.")
            return
        
        file_path, filter_type = QFileDialog.getOpenFileName(
            self, "Import Transactions",
            str(Path.home()),
            "QIF Files (*.qif);;CSV Files (*.csv);;OFX Files (*.ofx);;All Files (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            count = 0
            if file_path.endswith('.qif'):
                count = self.service.import_qif(file_path, self.current_account.id)
            elif file_path.endswith('.csv'):
                count = self.service.import_csv(file_path, self.current_account.id)
            elif file_path.endswith('.ofx'):
                count = self.service.import_ofx(file_path, self.current_account.id)
            else:
                QMessageBox.warning(self, "Unknown Format", "Please select a QIF, CSV, or OFX file.")
                return
            
            self.load_accounts(self.current_account.id)
            QMessageBox.information(self, "Import Complete", f"Imported {count} transactions.")
            self.statusBar().showMessage(f"Imported {count} transactions")
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Error importing file:\n{str(e)}")
    
    def export_transactions(self):
        """Export transactions to file."""
        if not self.current_account:
            QMessageBox.warning(self, "No Account", "Please select an account first.")
            return
        
        file_path, filter_type = QFileDialog.getSaveFileName(
            self, "Export Transactions",
            str(Path.home() / f"{self.current_account.name}.qif"),
            "QIF Files (*.qif);;CSV Files (*.csv);;All Files (*.*)"
        )
        
        if not file_path:
            return
        
        try:
            if file_path.endswith('.qif'):
                self.service.export_qif(file_path, self.current_account.id)
            elif file_path.endswith('.csv'):
                self.service.export_csv(file_path, self.current_account.id)
            else:
                QMessageBox.warning(self, "Unknown Format", "Please use .qif or .csv extension.")
                return
            
            QMessageBox.information(self, "Export Complete", f"Transactions exported to {file_path}")
            self.statusBar().showMessage("Export complete")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Error exporting file:\n{str(e)}")
    
    def manage_categories(self):
        """Open category management dialog."""
        dialog = CategoryDialog(self, self.service)
        dialog.exec()
    
    def show_settings(self):
        """Open settings dialog."""
        dialog = SettingsDialog(self, self.settings)
        if dialog.exec() == QDialog.Accepted:
            self.settings.save()
            # Refresh display with new currency
            self.load_accounts(self.current_account.id if self.current_account else None)
    
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            f"About {Config.APP_NAME}",
            f"{Config.APP_NAME} v{Config.APP_VERSION}\n\n"
            "A Microsoft Money 3.0 compatible personal finance application.\n\n"
            "Supports QIF, OFX, and CSV import/export."
        )
    
    def closeEvent(self, event):
        """Handle window close."""
        self.service.close()
        event.accept()


class AccountDialog(QDialog):
    """Dialog for creating/editing accounts."""
    
    def __init__(self, parent, account: Optional[Account] = None):
        super().__init__(parent)
        self.account = account
        self.init_ui()
    
    def init_ui(self):
        """Initialize dialog UI."""
        self.setWindowTitle("Account" if not self .account else "Edit Account")
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
        layout.addRow("Account Type:", self.type_combo)
        
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
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def get_data(self):
        """Get dialog data."""
        return {
            'name': self.name_edit.text(),
            'type': self.type_combo.currentData(),
            'opening_balance': Decimal(str(self.balance_spin.value()))
        }


class TransactionDialog(QDialog):
    """Dialog for creating/editing transactions."""
    
    def __init__(self, parent, service: MoneyService, account: Account, 
                 transaction: Optional[Transaction] = None):
        super().__init__(parent)
        self.service = service
        self.account = account
        self.transaction = transaction
        self.init_ui()
    
    def init_ui(self):
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
            self.date_edit.setDate(QDate(self.transaction.date.year, 
                                         self.transaction.date.month, 
                                         self.transaction.date.day))
        else:
            self.date_edit.setDate(QDate.currentDate())
        layout.addRow("Date:", self.date_edit)

        # Transaction type
        self.type_combo = QComboBox()
        self.type_combo.addItem("Deposit", "deposit")
        self.type_combo.addItem("Payment (Check)", "payment")
        if self.transaction and self.transaction.amount >= 0:
            self.type_combo.setCurrentIndex(0)
        else:
            self.type_combo.setCurrentIndex(1)
        layout.addRow("Type:", self.type_combo)
        
        # Check number
        self.check_edit = QLineEdit()
        if self.transaction:
            self.check_edit.setText(self.transaction.check_number)
        layout.addRow("Check #:", self.check_edit)
        
        # Payee
        self.payee_edit = QLineEdit()
        if self.transaction:
            self.payee_edit.setText(self.transaction.payee)
        layout.addRow("Payee:", self.payee_edit)
        
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
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        
        self.setLayout(layout)
    
    def get_data(self):
        """Get dialog data."""
        qdate = self.date_edit.date()
        amount = Decimal(str(self.amount_spin.value()))
        if self.type_combo.currentData() == "payment":
            amount = -amount

        return {
            'date': date(qdate.year(), qdate.month(), qdate.day()),
            'check_number': self.check_edit.text(),
            'payee': self.payee_edit.text(),
            'amount': amount,
            'status': self.status_combo.currentData(),
            'memo': self.memo_edit.text()
        }


class CategoryDialog(QDialog):
    """Dialog for managing categories."""
    
    def __init__(self, parent, service: MoneyService):
        super().__init__(parent)
        self.service = service
        self.init_ui()
        self.load_categories()
    
    def init_ui(self):
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
    
    def load_categories(self):
        """Load categories into list."""
        self.category_list.clear()
        categories = self.service.get_all_categories()
        for cat in categories:
            income_indicator = "(Income)" if cat.is_income else "(Expense)"
            self.category_list.addItem(f"{cat.name} {income_indicator}")
    
    def new_category(self):
        """Create new category."""
        name, ok = QLineEdit.getText(self, "New Category", "Category name:")
        if ok and name:
            self.service.create_category(name)
            self.load_categories()
    
    def delete_category(self):
        """Delete selected category."""
        row = self.category_list.currentRow()
        if row < 0:
            return
        
        categories = self.service.get_all_categories()
        if row < len(categories):
            category = categories[row]
            reply = QMessageBox.question(
                self, "Confirm Delete",
                f"Delete category '{category.name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.service.delete_category(category.id)
                self.load_categories()


class SettingsDialog(QDialog):
    """Dialog for application settings."""
    
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.settings = settings
        self.init_ui()
    
    def init_ui(self):
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
        self.preview_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border: 1px solid #ccc;")
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
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def update_preview(self):
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
    
    def accept(self):
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


def QLineEdit_getText(parent, title, label):
    """Simple helper for text input dialog."""
    from PySide6.QtWidgets import QInputDialog
    return QInputDialog.getText(parent, title, label)


# Monkey patch the helper
QLineEdit.getText = staticmethod(QLineEdit_getText)
