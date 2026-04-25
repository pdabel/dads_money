"""Investment account panel (holdings + transactions tabs)."""

from decimal import Decimal
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import Account, InvestmentTransaction, InvestmentTransactionType
from ..services import MoneyService
from .investment_dialogs import (
    CashReconcileDialog,
    InvestmentTransactionDialog,
    ManageSecuritiesDialog,
    PriceFetchWorker,
    PriceHistoryDialog,
    UpdatePriceDialog,
)


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
        btn_reconcile = QPushButton("Reconcile Cash")
        for btn in (btn_buy, btn_sell, btn_price, btn_fetch, btn_chart, btn_manage, btn_reconcile):
            btn_bar.addWidget(btn)
        btn_bar.addStretch()
        vbox.addLayout(btn_bar)

        btn_buy.clicked.connect(self._on_buy)
        btn_sell.clicked.connect(self._on_sell)
        btn_price.clicked.connect(self._on_update_price)
        btn_fetch.clicked.connect(self._on_fetch_prices)
        btn_chart.clicked.connect(self._on_view_chart)
        btn_manage.clicked.connect(self._on_manage_securities)
        btn_reconcile.clicked.connect(self._on_reconcile_cash)

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
        btn_duplicate = QPushButton("Duplicate")
        btn_delete = QPushButton("Delete")
        for btn in (btn_new, btn_edit, btn_duplicate, btn_delete):
            btn_bar.addWidget(btn)
        btn_bar.addStretch()
        vbox.addLayout(btn_bar)

        btn_new.clicked.connect(self._on_new_txn)
        btn_edit.clicked.connect(self._on_edit_txn)
        btn_duplicate.clicked.connect(self._on_duplicate_txn)
        btn_delete.clicked.connect(self._on_delete_txn)

        self.txn_table = QTableWidget()
        self.txn_table.setColumnCount(len(self.TXN_COLUMNS))
        self.txn_table.setHorizontalHeaderLabels(self.TXN_COLUMNS)
        self.txn_table.setSelectionBehavior(QTableWidget.SelectRows)  # type: ignore[attr-defined]
        self.txn_table.setSelectionMode(QTableWidget.ExtendedSelection)  # type: ignore[attr-defined]
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
        # Keep the account list panel in sync
        win = self.window()
        if hasattr(win, "_refresh_account_list_item"):
            win._refresh_account_list_item(self.account.id)

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
                # Use up to 6 decimal places for unit prices, stripping trailing zeros
                # but keeping at least the currency's standard decimal places.
                min_dp = self.settings.decimal_places
                price_str = f"{h.current_price:.6f}".rstrip("0")
                if "." in price_str:
                    integer_part, frac_part = price_str.split(".")
                    frac_part = frac_part.ljust(min_dp, "0")
                    price_str = f"{integer_part}.{frac_part}"
                price_str = self.settings.currency_symbol + price_str
                self.holdings_table.setItem(row, 5, _cell(price_str, right))
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
            transfer_account_id = data.pop("transfer_account_id", None)

            # If proceeds are transferred out, zero the cash impact on this account
            # after creation (service always computes amount from qty/price).
            if txn is None:
                new_txn = self.service.create_investment_transaction(**data)
            else:
                for k, v in data.items():
                    setattr(txn, k, v)
                self.service.update_investment_transaction(txn)
                new_txn = txn

            if transfer_account_id:
                new_txn.amount = Decimal("0")
                self.service.update_investment_transaction(new_txn, force_amount=Decimal("0"))

            # Create a matching deposit in the target account.
            if transfer_account_id:
                qty = data.get("quantity", Decimal("0"))
                price = data.get("price", Decimal("0"))
                commission = data.get("commission", Decimal("0"))
                proceeds = qty * price - commission if (qty and price) else Decimal("0")
                security_name = ""
                if data.get("security_id"):
                    sec = next(
                        (
                            s
                            for s in self.service.get_all_securities()
                            if s.id == data["security_id"]
                        ),
                        None,
                    )
                    if sec:
                        security_name = sec.name
                self.service.create_transaction(
                    account_id=transfer_account_id,
                    date=data["txn_date"],
                    amount=float(proceeds),
                    payee=f"Sale: {security_name}".strip(": "),
                    memo=data.get("memo", ""),
                    status=data.get("status"),
                )

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
        tickers = [(s.id, s.ticker_symbol, s.currency) for s in securities if s.ticker_symbol]
        if not tickers:
            QMessageBox.information(
                self,
                "No Tickers",
                "No securities have ticker symbols set.\n" "Edit a security to add a ticker.",
            )
            return
        self._fetch_worker = PriceFetchWorker(tickers, self.service)
        self._fetch_worker.price_fetched.connect(self._on_price_fetched)
        self._fetch_worker.finished.connect(self._on_fetch_done)
        self._fetch_worker.error.connect(self._on_fetch_error)
        self._fetch_worker.start()
        self.statusBar_message("Fetching prices…")

    def statusBar_message(self, msg: str) -> None:  # noqa: N802
        win = self.window()
        if hasattr(win, "statusBar"):
            win.statusBar().showMessage(msg)

    def _on_price_fetched(self, security_id: str, price: object) -> None:
        """Save a single fetched price on the main thread (SQLite thread-safety)."""
        from datetime import date as _date
        from decimal import Decimal

        self.service.add_security_price(
            security_id, _date.today(), Decimal(str(price)), source="api"
        )

    def _on_fetch_done(self, updated: int, failed: list) -> None:
        msg = f"Fetched prices for {updated} security/securities."
        if failed:
            msg += f"\n\nCould not fetch: {', '.join(failed)}\n\nTip: UK stocks need a .L suffix (e.g. LLOY.L). Edit the security to correct the ticker symbol."
            QMessageBox.warning(self, "Some Prices Not Found", msg)
        else:
            self.statusBar_message(msg)
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

    def _on_reconcile_cash(self) -> None:
        summary = self.service.get_portfolio_summary(self.account.id)
        dialog = CashReconcileDialog(self, summary.cash_balance, self.settings)
        if dialog.exec() == QDialog.Accepted:  # type: ignore[attr-defined]
            stmt_date, adjustment, memo = dialog.get_data()
            if adjustment == Decimal("0"):
                QMessageBox.information(
                    self,
                    "No Adjustment Needed",
                    "The calculated balance already matches the statement balance.",
                )
                return
            from ..models import InvestmentTransactionType, TransactionStatus

            txn_type = (
                InvestmentTransactionType.MISC_INC
                if adjustment > Decimal("0")
                else InvestmentTransactionType.MISC_EXP
            )
            self.service.create_investment_transaction(
                account_id=self.account.id,
                transaction_type=txn_type,
                txn_date=stmt_date,
                security_id=None,
                quantity=Decimal("0"),
                price=abs(adjustment),
                commission=Decimal("0"),
                memo=memo or "Cash reconciliation adjustment",
                status=TransactionStatus.RECONCILED,
            )
            self.refresh()
            self.statusBar_message(
                f"Cash balance adjusted by {self.settings.format_currency(adjustment)}."
            )

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

    def _on_duplicate_txn(self) -> None:
        row = self.txn_table.currentRow()
        if row < 0:
            return
        item = self.txn_table.item(row, 0)
        if not item:
            return
        txn_id = item.data(Qt.UserRole)  # type: ignore[attr-defined]
        txn = self.service.get_investment_transaction(txn_id)
        if not txn:
            return
        dialog = InvestmentTransactionDialog(self, self.service, self.account, txn)
        dialog.setWindowTitle("Duplicate Investment Transaction")
        if dialog.exec() == QDialog.Accepted:  # type: ignore[attr-defined]
            data = dialog.get_data()
            data.pop("transfer_account_id", None)
            self.service.create_investment_transaction(**data)
            self.refresh()

    def _on_delete_txn(self) -> None:
        selected_rows = self.txn_table.selectionModel().selectedRows()
        if not selected_rows:
            return
        # Collect unique transaction IDs from column 0 of each selected row
        txn_ids = []
        for index in selected_rows:
            item = self.txn_table.item(index.row(), 0)
            if item:
                txn_ids.append(item.data(Qt.UserRole))  # type: ignore[attr-defined]
        if not txn_ids:
            return
        n = len(txn_ids)
        reply = QMessageBox.question(
            self,
            "Delete Transaction" + ("s" if n > 1 else ""),
            f"Delete {n} investment transaction{'s' if n > 1 else ''}?",
            QMessageBox.Yes | QMessageBox.No,  # type: ignore[attr-defined]
        )
        if reply == QMessageBox.Yes:  # type: ignore[attr-defined]
            for txn_id in txn_ids:
                self.service.delete_investment_transaction(txn_id, self.account.id)
            self.refresh()
