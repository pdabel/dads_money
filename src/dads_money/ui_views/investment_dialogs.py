"""Investment-related dialogs and background worker thread."""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QDate, QLocale, QTime, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..models import (
    Account,
    Security,
    SecurityPrice,
    SecurityType,
    InvestmentTransaction,
    InvestmentTransactionType,
    TransactionStatus,
)
from ..services import MoneyService
from ..settings import get_settings


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
        self.date_edit.setDisplayFormat(settings.qt_date_format)
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
        self.qty_spin.setLocale(QLocale.c())
        layout.addRow(self.qty_label, self.qty_spin)

        # Price per share
        self.price_label = QLabel("Price per Share:")
        self.price_spin = QDoubleSpinBox()
        self.price_spin.setDecimals(5)
        self.price_spin.setRange(0, 1_000_000_000)
        self.price_spin.setLocale(QLocale.c())
        self.price_spin.setPrefix(settings.currency_symbol + " ")
        layout.addRow(self.price_label, self.price_spin)

        # Commission
        self.commission_label = QLabel("Commission:")
        self.commission_spin = QDoubleSpinBox()
        self.commission_spin.setDecimals(settings.decimal_places)
        self.commission_spin.setRange(0, 1_000_000)
        self.commission_spin.setLocale(QLocale.c())
        self.commission_spin.setPrefix(settings.currency_symbol + " ")
        layout.addRow(self.commission_label, self.commission_spin)

        # Cash amount override for income-type entries
        self.amount_label = QLabel("Amount:")
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setDecimals(settings.decimal_places)
        self.amount_spin.setRange(0, 1_000_000_000)
        self.amount_spin.setLocale(QLocale.c())
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

        # Transfer proceeds to account (Sell only)
        self.transfer_label = QLabel("Transfer proceeds to:")
        self.transfer_combo = QComboBox()
        self.transfer_combo.addItem("— Keep as cash —", None)
        for acct in self.service.get_all_accounts():
            if acct.id != self.account.id:
                self.transfer_combo.addItem(f"{acct.name} ({acct.account_type.value})", acct.id)
        layout.addRow(self.transfer_label, self.transfer_combo)

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
        is_income = txn_type not in _NEEDS_QTY
        is_sell = txn_type == InvestmentTransactionType.SELL

        for w in (self.qty_label, self.qty_spin, self.price_label, self.price_spin):
            w.setVisible(needs_qty)
        for w in (self.commission_label, self.commission_spin):
            w.setVisible(needs_commission)
        for w in (self.amount_label, self.amount_spin):
            w.setVisible(is_income)
        for w in (self.transfer_label, self.transfer_combo):
            w.setVisible(is_sell)

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

        transfer_account_id = (
            self.transfer_combo.currentData()
            if txn_type == InvestmentTransactionType.SELL
            else None
        )

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
            "transfer_account_id": transfer_account_id,
        }


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
        self.ticker_edit.setPlaceholderText("Yahoo Finance format, e.g. AAPL, LLOY.L (optional)")
        layout.addRow("Ticker Symbol:", self.ticker_edit)

        self.type_combo = QComboBox()
        for st in SecurityType:
            self.type_combo.addItem(st.value, st)
        layout.addRow("Type:", self.type_combo)

        # Currency of the security's native price (empty = same as app currency)
        from ..settings import CURRENCIES

        self.currency_combo = QComboBox()
        self.currency_combo.addItem("(Same as app currency)", "")
        for code, info in sorted(CURRENCIES.items()):
            self.currency_combo.addItem(f"{code} — {info['name']} ({info['symbol']})", code)
        layout.addRow("Native Currency:", self.currency_combo)

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
        cur_idx = self.currency_combo.findData(sec.currency)
        if cur_idx >= 0:
            self.currency_combo.setCurrentIndex(cur_idx)
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
            "currency": self.currency_combo.currentData() or "",
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
            sec.currency = d["currency"]
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


class UpdatePriceDialog(QDialog):
    """Dialog for manually entering a price for a security."""

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
        self.date_edit.setDisplayFormat(settings.qt_date_format)
        layout.addRow("Date:", self.date_edit)

        self.price_spin = QDoubleSpinBox()
        self.price_spin.setDecimals(6)
        self.price_spin.setRange(0, 1_000_000_000)
        self.price_spin.setLocale(QLocale.c())
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


class CashReconcileDialog(QDialog):
    """Reconcile an investment account's cash balance against a statement.

    Creates a single adjustment transaction for the difference so the
    calculated cash balance matches the user's statement value.
    """

    def __init__(self, parent: Any, current_balance: Decimal, settings: Any) -> None:
        super().__init__(parent)
        self._current = current_balance
        self._settings = settings
        self.setWindowTitle("Reconcile Cash Balance")
        self.setModal(True)
        self.setMinimumWidth(360)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QFormLayout(self)

        layout.addRow(
            QLabel(f"Current cash balance: <b>{self._settings.format_currency(self._current)}</b>")
        )

        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat(self._settings.qt_date_format)
        layout.addRow("Statement date:", self.date_edit)

        self.statement_spin = QDoubleSpinBox()
        self.statement_spin.setDecimals(self._settings.decimal_places)
        self.statement_spin.setRange(-1_000_000_000, 1_000_000_000)
        self.statement_spin.setLocale(QLocale.c())
        self.statement_spin.setPrefix(self._settings.currency_symbol + " ")
        self.statement_spin.setValue(float(self._current))
        layout.addRow("Statement balance:", self.statement_spin)

        self.adjustment_label = QLabel(self._fmt_adjustment())
        layout.addRow("Adjustment:", self.adjustment_label)

        self.memo_edit = QLineEdit()
        self.memo_edit.setText("Cash reconciliation adjustment")
        layout.addRow("Memo:", self.memo_edit)

        self.statement_spin.valueChanged.connect(self._update_adjustment_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel  # type: ignore[attr-defined]
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _adjustment(self) -> Decimal:
        return Decimal(str(self.statement_spin.value())) - self._current

    def _fmt_adjustment(self) -> str:
        adj = self._adjustment()
        return self._settings.format_currency(adj)

    def _update_adjustment_label(self) -> None:
        self.adjustment_label.setText(self._fmt_adjustment())

    def get_data(self) -> tuple[date, Decimal, str]:
        """Return (statement_date, adjustment_amount, memo)."""
        qd = self.date_edit.date()
        stmt_date = date(qd.year(), qd.month(), qd.day())
        return stmt_date, self._adjustment(), self.memo_edit.text().strip()


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


class PriceFetchWorker(QThread):
    """Fetches prices from yfinance in a background thread.

    Prices are emitted via ``price_fetched`` so the main thread can save them
    to SQLite (SQLite connections must not be shared across threads).
    """

    # emitted for each successfully fetched price: (security_id, price)
    price_fetched = Signal(str, object)
    finished = Signal(int, list)  # (number updated, list of failed ticker strings)
    error = Signal(str)  # error message if yfinance unavailable

    def __init__(self, tickers: List[tuple[str, str, str]], service: MoneyService) -> None:
        super().__init__()
        self.tickers = tickers  # list of (security_id, ticker_symbol, security_currency)
        self.service = service

    def run(self) -> None:
        updated = 0
        failed: List[str] = []
        for security_id, ticker, security_currency in self.tickers:
            try:
                price = self.service.fetch_price_from_api(ticker, security_currency)
            except ImportError as exc:
                self.error.emit(str(exc))
                return
            if price is not None:
                self.price_fetched.emit(security_id, price)
                updated += 1
            else:
                failed.append(ticker)
        self.finished.emit(updated, failed)
