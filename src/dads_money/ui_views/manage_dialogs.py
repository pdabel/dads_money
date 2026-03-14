"""Category and payee management dialogs."""

from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..services import MoneyService


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
