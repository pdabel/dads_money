"""Application settings dialog."""

from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from ..settings import CURRENCIES


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
