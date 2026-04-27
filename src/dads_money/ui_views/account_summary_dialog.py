"""Account Summary Report dialog.

Provides a summary of selected accounts over either a UK tax year
(6 Apr – 5 Apr) or a custom date range.  For each account it shows the
opening balance, total credits, total debits, net change, closing balance,
and a per-category breakdown.
"""

from datetime import date as Date
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QFont, QPageLayout, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import AccountSummaryReport, Account, AccountType, SavingsAccountType
from ..services import MoneyService
from ..settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CURRENT_TAX_YEAR_START: int = (
    Date.today().year - 1
    if Date.today().month < 4 or (Date.today().month == 4 and Date.today().day < 6)
    else Date.today().year
)


def _tax_year_label(year_start: int) -> str:
    return f"{year_start}/{str(year_start + 1)[-2:]}"


def _tax_year_dates(year_start: int) -> tuple:
    return Date(year_start, 4, 6), Date(year_start + 1, 4, 5)


# ---------------------------------------------------------------------------
# Reusable account selector (mirrors the one in tax_report_dialog)
# ---------------------------------------------------------------------------


class _AccountSelector(QWidget):
    """Scrollable list of checkboxes — one per account."""

    def __init__(self, accounts: List[Account], parent: Any = None) -> None:
        super().__init__(parent)
        self._checkboxes: List[tuple] = []

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        btn_row = QHBoxLayout()
        all_btn = QPushButton("Select All")
        none_btn = QPushButton("Select None")
        all_btn.clicked.connect(self._select_all)
        none_btn.clicked.connect(self._select_none)
        btn_row.addWidget(all_btn)
        btn_row.addWidget(none_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # type: ignore[attr-defined]

        inner = QWidget()
        inner_layout = QVBoxLayout()
        inner_layout.setSpacing(2)

        for account in sorted(accounts, key=lambda a: (a.account_type.value, a.name)):
            label = account.name
            if account.owner:
                label += f"  [{account.owner}]"
            cb = QCheckBox(label)
            cb.setChecked(True)
            self._checkboxes.append((account, cb))
            inner_layout.addWidget(cb)

        inner_layout.addStretch()
        inner.setLayout(inner_layout)
        scroll.setWidget(inner)
        layout.addWidget(scroll)
        self.setLayout(layout)

    def _select_all(self) -> None:
        for _, cb in self._checkboxes:
            cb.setChecked(True)

    def _select_none(self) -> None:
        for _, cb in self._checkboxes:
            cb.setChecked(False)

    def selected_account_ids(self) -> List[str]:
        return [acc.id for acc, cb in self._checkboxes if cb.isChecked()]


# ---------------------------------------------------------------------------
# Report results widget
# ---------------------------------------------------------------------------


def _make_amount_item(
    sym: str, amount: Decimal, *, bold: bool = False, negative_red: bool = False
) -> QTableWidgetItem:
    item = QTableWidgetItem(f"{sym}{amount:,.2f}")
    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[attr-defined]
    if bold:
        font = QFont()
        font.setBold(True)
        item.setFont(font)
    if negative_red and amount < Decimal("0"):
        from PySide6.QtGui import QColor

        item.setForeground(QColor("red"))
    return item


class _SummaryResultsWidget(QWidget):
    """Renders an AccountSummaryReport in tabbed sections."""

    def __init__(
        self,
        report: AccountSummaryReport,
        settings: Settings,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self._report = report
        self._settings = settings
        self._sym = settings.currency_symbol
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout()

        title = QLabel(f"Account Summary — {self._report.period_label}")
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        title.setFont(font)
        title.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        outer.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_overview_tab(), "Overview")
        tabs.addTab(self._build_category_tab(), "By Category")
        outer.addWidget(tabs)

        self.setLayout(outer)

    # ----------------------------------------------------------------
    # Overview tab  — one row per account
    # ----------------------------------------------------------------

    def _build_overview_tab(self) -> QWidget:
        r = self._report
        sym = self._sym
        cols = [
            "Account",
            "Type",
            "Opening Balance",
            "Credits",
            "Debits",
            "Net Change",
            "Closing Balance",
            "Transactions",
        ]
        rows = len(r.entries) + 1  # +1 for totals row
        table = QTableWidget(rows, len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)  # type: ignore[attr-defined]
        table.setAlternatingRowColors(True)

        for row, entry in enumerate(r.entries):
            table.setItem(row, 0, QTableWidgetItem(entry.account_name))
            table.setItem(row, 1, QTableWidgetItem(entry.account_type))
            table.setItem(row, 2, _make_amount_item(sym, entry.opening_balance))
            table.setItem(row, 3, _make_amount_item(sym, entry.total_credits))
            table.setItem(row, 4, _make_amount_item(sym, entry.total_debits))
            net_item = _make_amount_item(sym, entry.net_change, negative_red=True)
            table.setItem(row, 5, net_item)
            table.setItem(row, 6, _make_amount_item(sym, entry.closing_balance))
            cnt_item = QTableWidgetItem(str(entry.transaction_count))
            cnt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[attr-defined]
            table.setItem(row, 7, cnt_item)

        # Totals row
        total_row = len(r.entries)
        total_credits = r.total_credits
        total_debits = r.total_debits
        net = r.net_change
        total_txns = sum(e.transaction_count for e in r.entries)

        totals_label = QTableWidgetItem("TOTALS")
        font = QFont()
        font.setBold(True)
        totals_label.setFont(font)
        table.setItem(total_row, 0, totals_label)
        table.setItem(total_row, 1, QTableWidgetItem(""))
        table.setItem(total_row, 2, QTableWidgetItem(""))
        table.setItem(total_row, 3, _make_amount_item(sym, total_credits, bold=True))
        table.setItem(total_row, 4, _make_amount_item(sym, total_debits, bold=True))
        table.setItem(total_row, 5, _make_amount_item(sym, net, bold=True, negative_red=True))
        table.setItem(total_row, 6, QTableWidgetItem(""))
        cnt_total = QTableWidgetItem(str(total_txns))
        cnt_total.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[attr-defined]
        font2 = QFont()
        font2.setBold(True)
        cnt_total.setFont(font2)
        table.setItem(total_row, 7, cnt_total)

        table.resizeColumnsToContents()
        w = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(table)
        w.setLayout(layout)
        return w

    # ----------------------------------------------------------------
    # Category tab  — combined across all selected accounts
    # ----------------------------------------------------------------

    def _build_category_tab(self) -> QWidget:
        sym = self._sym
        r = self._report

        # Aggregate category totals across all accounts
        cat_totals: Dict[str, Decimal] = {}
        for entry in r.entries:
            for row in entry.category_breakdown:
                cat_totals[row.category_name] = (
                    cat_totals.get(row.category_name, Decimal("0")) + row.amount
                )

        # Split into income (>0) and expense (<0) groups
        income_items = sorted(
            [(k, v) for k, v in cat_totals.items() if v > Decimal("0")],
            key=lambda x: x[0],
        )
        expense_items = sorted(
            [(k, v) for k, v in cat_totals.items() if v < Decimal("0")],
            key=lambda x: x[0],
        )

        tabs = QTabWidget()

        # Income sub-tab
        inc_cols = ["Category", "Amount"]
        inc_rows = len(income_items) + (1 if income_items else 0)
        t_inc = QTableWidget(inc_rows, 2)
        t_inc.setHorizontalHeaderLabels(inc_cols)
        t_inc.verticalHeader().setVisible(False)
        t_inc.setEditTriggers(QTableWidget.NoEditTriggers)  # type: ignore[attr-defined]
        t_inc.setAlternatingRowColors(True)
        for i, (cat, amount) in enumerate(income_items):
            t_inc.setItem(i, 0, QTableWidgetItem(cat))
            t_inc.setItem(i, 1, _make_amount_item(sym, amount))
        if income_items:
            total_inc = sum(v for _, v in income_items)
            tot_row = len(income_items)
            tot_lbl = QTableWidgetItem("Total Income")
            font = QFont()
            font.setBold(True)
            tot_lbl.setFont(font)
            t_inc.setItem(tot_row, 0, tot_lbl)
            t_inc.setItem(tot_row, 1, _make_amount_item(sym, total_inc, bold=True))
        t_inc.horizontalHeader().setStretchLastSection(True)
        t_inc.resizeColumnsToContents()
        w_inc = QWidget()
        l_inc = QVBoxLayout()
        l_inc.addWidget(t_inc)
        w_inc.setLayout(l_inc)
        tabs.addTab(w_inc, "Income")

        # Expense sub-tab
        exp_cols = ["Category", "Amount"]
        exp_rows = len(expense_items) + (1 if expense_items else 0)
        t_exp = QTableWidget(exp_rows, 2)
        t_exp.setHorizontalHeaderLabels(exp_cols)
        t_exp.verticalHeader().setVisible(False)
        t_exp.setEditTriggers(QTableWidget.NoEditTriggers)  # type: ignore[attr-defined]
        t_exp.setAlternatingRowColors(True)
        for i, (cat, amount) in enumerate(expense_items):
            t_exp.setItem(i, 0, QTableWidgetItem(cat))
            t_exp.setItem(i, 1, _make_amount_item(sym, abs(amount)))
        if expense_items:
            total_exp = sum(abs(v) for _, v in expense_items)
            tot_row = len(expense_items)
            tot_lbl = QTableWidgetItem("Total Expenses")
            font = QFont()
            font.setBold(True)
            tot_lbl.setFont(font)
            t_exp.setItem(tot_row, 0, tot_lbl)
            t_exp.setItem(tot_row, 1, _make_amount_item(sym, total_exp, bold=True))
        t_exp.horizontalHeader().setStretchLastSection(True)
        t_exp.resizeColumnsToContents()
        w_exp = QWidget()
        l_exp = QVBoxLayout()
        l_exp.addWidget(t_exp)
        w_exp.setLayout(l_exp)
        tabs.addTab(w_exp, "Expenses")

        outer = QWidget()
        outer_layout = QVBoxLayout()
        outer_layout.addWidget(tabs)
        outer.setLayout(outer_layout)
        return outer


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------


class AccountSummaryDialog(QDialog):
    """Dialog for generating an account summary report."""

    def __init__(self, parent: Any, service: MoneyService, settings: Settings) -> None:
        super().__init__(parent)
        self.service = service
        self.settings = settings
        self._report: Optional[AccountSummaryReport] = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("Account Summary Report")
        self.setModal(True)
        self.setMinimumSize(920, 640)

        outer = QVBoxLayout()

        # ---- period options ----
        period_box = QGroupBox("Report Period")
        period_layout = QVBoxLayout()

        mode_row = QHBoxLayout()
        self._rb_tax_year = QRadioButton("UK Tax Year")
        self._rb_custom = QRadioButton("Custom Date Range")
        self._rb_tax_year.setChecked(True)
        mode_row.addWidget(self._rb_tax_year)
        mode_row.addWidget(self._rb_custom)
        mode_row.addStretch()
        period_layout.addLayout(mode_row)

        # Stacked widget: page 0 = tax year, page 1 = custom range
        self._period_stack = QStackedWidget()

        # Page 0 — tax year
        ty_page = QWidget()
        ty_layout = QHBoxLayout()
        ty_layout.setContentsMargins(0, 0, 0, 0)
        ty_layout.addWidget(QLabel("Tax Year:"))
        self._year_combo = QComboBox()
        current_year = _CURRENT_TAX_YEAR_START
        for y in range(current_year, current_year - 10, -1):
            self._year_combo.addItem(_tax_year_label(y), y)
        ty_layout.addWidget(self._year_combo)
        ty_layout.addStretch()
        ty_page.setLayout(ty_layout)
        self._period_stack.addWidget(ty_page)

        # Page 1 — custom range
        cr_page = QWidget()
        cr_layout = QHBoxLayout()
        cr_layout.setContentsMargins(0, 0, 0, 0)
        cr_layout.addWidget(QLabel("From:"))
        self._date_from = QDateEdit()
        self._date_from.setCalendarPopup(True)
        self._date_from.setDisplayFormat("dd/MM/yyyy")
        self._date_from.setDate(QDate(Date.today().year, 1, 1))
        cr_layout.addWidget(self._date_from)
        cr_layout.addWidget(QLabel("To:"))
        self._date_to = QDateEdit()
        self._date_to.setCalendarPopup(True)
        self._date_to.setDisplayFormat("dd/MM/yyyy")
        self._date_to.setDate(QDate.currentDate())
        cr_layout.addWidget(self._date_to)
        cr_layout.addStretch()
        cr_page.setLayout(cr_layout)
        self._period_stack.addWidget(cr_page)

        period_layout.addWidget(self._period_stack)
        period_box.setLayout(period_layout)

        # Wire radio buttons to stack
        self._rb_tax_year.toggled.connect(
            lambda checked: self._period_stack.setCurrentIndex(0 if checked else 1)
        )

        # ---- action buttons ----
        btn_row = QHBoxLayout()
        generate_btn = QPushButton("Generate Report")
        generate_btn.clicked.connect(self._generate)
        generate_btn.setDefault(True)
        btn_row.addWidget(generate_btn)
        btn_row.addStretch()
        export_btn = QPushButton("Export to Text…")
        export_btn.clicked.connect(self._export_text)
        btn_row.addWidget(export_btn)
        print_preview_btn = QPushButton("Print Preview…")
        print_preview_btn.clicked.connect(self._print_preview)
        btn_row.addWidget(print_preview_btn)
        print_btn = QPushButton("Print…")
        print_btn.clicked.connect(self._print_report)
        btn_row.addWidget(print_btn)

        outer.addWidget(period_box)
        outer.addLayout(btn_row)

        # ---- splitter: accounts on left, results on right ----
        splitter = QSplitter(Qt.Horizontal)  # type: ignore[attr-defined]

        accounts = self.service.get_all_accounts(include_closed=False, include_hidden=False)
        acct_group = QGroupBox("Include Accounts")
        acct_layout = QVBoxLayout()
        self._account_selector = _AccountSelector(accounts)
        acct_layout.addWidget(self._account_selector)
        acct_group.setLayout(acct_layout)
        acct_group.setMinimumWidth(240)
        splitter.addWidget(acct_group)

        self._results_container = QWidget()
        results_layout = QVBoxLayout()
        self._placeholder_label = QLabel(
            'Select accounts and a period, then click "Generate Report".'
        )
        self._placeholder_label.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        self._placeholder_label.setWordWrap(True)
        results_layout.addWidget(self._placeholder_label)
        self._results_container.setLayout(results_layout)
        splitter.addWidget(self._results_container)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        outer.addWidget(splitter)

        btn_box = QDialogButtonBox(QDialogButtonBox.Close)  # type: ignore[attr-defined]
        btn_box.rejected.connect(self.reject)
        outer.addWidget(btn_box)

        self.setLayout(outer)

    # ----------------------------------------------------------------
    # Actions
    # ----------------------------------------------------------------

    def _resolve_dates(self) -> tuple:
        """Return (start_date, end_date) based on current period selection."""
        if self._rb_tax_year.isChecked():
            year_start: int = self._year_combo.currentData()
            return _tax_year_dates(year_start)
        else:
            qd_from = self._date_from.date()
            qd_to = self._date_to.date()
            start = Date(qd_from.year(), qd_from.month(), qd_from.day())
            end = Date(qd_to.year(), qd_to.month(), qd_to.day())
            return start, end

    def _generate(self) -> None:
        account_ids = self._account_selector.selected_account_ids()
        if not account_ids:
            QMessageBox.warning(self, "No Accounts", "Please select at least one account.")
            return

        start_date, end_date = self._resolve_dates()
        if end_date < start_date:
            QMessageBox.warning(
                self, "Invalid Date Range", "End date must be on or after start date."
            )
            return

        try:
            report = self.service.generate_account_summary(start_date, end_date, account_ids)
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to generate report:\n{exc}")
            return

        self._report = report
        self._show_results(report)

    def _show_results(self, report: AccountSummaryReport) -> None:
        layout = self._results_container.layout()
        if layout is None:
            return
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        results_widget = _SummaryResultsWidget(report, self.settings, self._results_container)
        layout.addWidget(results_widget)

    def _print_report(self) -> None:
        if self._report is None:
            QMessageBox.information(self, "No Report", "Please generate a report first.")
            return
        printer = QPrinter(QPrinter.HighResolution)  # type: ignore[attr-defined]
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() == QPrintDialog.Accepted:  # type: ignore[attr-defined]
            doc = QTextDocument()
            doc.setHtml(_render_report_as_html(self._report, self.settings))
            doc.print_(printer)

    def _print_preview(self) -> None:
        if self._report is None:
            QMessageBox.information(self, "No Report", "Please generate a report first.")
            return
        printer = QPrinter(QPrinter.HighResolution)  # type: ignore[attr-defined]
        printer.setPageOrientation(QPageLayout.Orientation.Landscape)
        preview = QPrintPreviewDialog(printer, self)
        preview.setMinimumSize(900, 650)
        preview.paintRequested.connect(self._do_print)
        preview.exec()

    def _do_print(self, printer: QPrinter) -> None:
        if self._report is None:
            return
        doc = QTextDocument()
        doc.setHtml(_render_report_as_html(self._report, self.settings))
        doc.print_(printer)

    def _export_text(self) -> None:
        if self._report is None:
            QMessageBox.information(self, "No Report", "Please generate a report first.")
            return

        safe_period = self._report.period_label.replace(" – ", "_to_").replace(" ", "-")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Account Summary Report",
            str(Path.home() / f"account_summary_{safe_period}.txt"),
            "Text Files (*.txt);;All Files (*.*)",
        )
        if not file_path:
            return

        try:
            text = _render_report_as_text(self._report, self.settings)
            Path(file_path).write_text(text, encoding="utf-8")
            QMessageBox.information(self, "Exported", f"Report saved to:\n{file_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save report:\n{exc}")


# ---------------------------------------------------------------------------
# Plain-text renderer
# ---------------------------------------------------------------------------


def _render_report_as_text(report: AccountSummaryReport, settings: Settings) -> str:
    sym = settings.currency_symbol
    lines: List[str] = []

    def _section(title: str) -> None:
        lines.append("")
        lines.append("=" * 80)
        lines.append(f"  {title}")
        lines.append("=" * 80)

    lines.append(f"ACCOUNT SUMMARY REPORT")
    lines.append(f"Period: {report.period_label}")
    lines.append(f"Generated: {Date.today().strftime(settings.date_format)}")

    _section("OVERVIEW")
    w = [24, 18, 14, 14, 14, 14, 14, 8]
    header = (
        f"{'Account':<24}  {'Type':<18}  {'Opening':>14}  {'Credits':>14}"
        f"  {'Debits':>14}  {'Net Change':>14}  {'Closing':>14}  {'Txns':>8}"
    )
    lines.append(header)
    lines.append("-" * 126)

    for entry in report.entries:
        lines.append(
            f"{entry.account_name:<24}  {entry.account_type:<18}"
            f"  {sym}{entry.opening_balance:>13,.2f}"
            f"  {sym}{entry.total_credits:>13,.2f}"
            f"  {sym}{entry.total_debits:>13,.2f}"
            f"  {sym}{entry.net_change:>13,.2f}"
            f"  {sym}{entry.closing_balance:>13,.2f}"
            f"  {entry.transaction_count:>8}"
        )

    lines.append("-" * 126)
    lines.append(
        f"{'TOTALS':<24}  {'':18}"
        f"  {'':>14}"
        f"  {sym}{report.total_credits:>13,.2f}"
        f"  {sym}{report.total_debits:>13,.2f}"
        f"  {sym}{report.net_change:>13,.2f}"
        f"  {'':>14}"
        f"  {sum(e.transaction_count for e in report.entries):>8}"
    )

    # Category breakdown
    _section("INCOME BY CATEGORY")
    cat_totals: Dict[str, Decimal] = {}
    for entry in report.entries:
        for row in entry.category_breakdown:
            cat_totals[row.category_name] = (
                cat_totals.get(row.category_name, Decimal("0")) + row.amount
            )

    income_cats = [(k, v) for k, v in sorted(cat_totals.items()) if v > Decimal("0")]
    if income_cats:
        for cat, amt in income_cats:
            lines.append(f"  {cat:<40}  {sym}{amt:>12,.2f}")
        lines.append(f"  {'Total':<40}  {sym}{sum(v for _, v in income_cats):>12,.2f}")
    else:
        lines.append("  (none)")

    _section("EXPENSES BY CATEGORY")
    expense_cats = [(k, abs(v)) for k, v in sorted(cat_totals.items()) if v < Decimal("0")]
    if expense_cats:
        for cat, amt in expense_cats:
            lines.append(f"  {cat:<40}  {sym}{amt:>12,.2f}")
        lines.append(f"  {'Total':<40}  {sym}{sum(v for _, v in expense_cats):>12,.2f}")
    else:
        lines.append("  (none)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML renderer (for print / print preview)
# ---------------------------------------------------------------------------


def _render_report_as_html(report: AccountSummaryReport, settings: Settings) -> str:
    sym = settings.currency_symbol

    def _amt(v: Decimal) -> str:
        colour = "red" if v < Decimal("0") else "inherit"
        return f'<span style="color:{colour}">{sym}{v:,.2f}</span>'

    rows_html = ""
    for entry in report.entries:
        rows_html += (
            f"<tr>"
            f"<td>{entry.account_name}</td>"
            f"<td>{entry.account_type}</td>"
            f"<td align='right'>{_amt(entry.opening_balance)}</td>"
            f"<td align='right'>{_amt(entry.total_credits)}</td>"
            f"<td align='right'>{_amt(entry.total_debits)}</td>"
            f"<td align='right'>{_amt(entry.net_change)}</td>"
            f"<td align='right'>{_amt(entry.closing_balance)}</td>"
            f"<td align='right'>{entry.transaction_count}</td>"
            f"</tr>"
        )

    rows_html += (
        f"<tr style='font-weight:bold;border-top:2px solid #333'>"
        f"<td colspan='3'>TOTALS</td>"
        f"<td align='right'>{_amt(report.total_credits)}</td>"
        f"<td align='right'>{_amt(report.total_debits)}</td>"
        f"<td align='right'>{_amt(report.net_change)}</td>"
        f"<td colspan='2'></td>"
        f"</tr>"
    )

    # Aggregate category totals
    cat_totals: Dict[str, Decimal] = {}
    for entry in report.entries:
        for row in entry.category_breakdown:
            cat_totals[row.category_name] = (
                cat_totals.get(row.category_name, Decimal("0")) + row.amount
            )

    income_rows = ""
    for cat, amt in sorted(cat_totals.items()):
        if amt > Decimal("0"):
            income_rows += f"<tr><td>{cat}</td><td align='right'>{_amt(amt)}</td></tr>"
    if not income_rows:
        income_rows = "<tr><td colspan='2'><i>(none)</i></td></tr>"

    expense_rows = ""
    for cat, amt in sorted(cat_totals.items()):
        if amt < Decimal("0"):
            expense_rows += f"<tr><td>{cat}</td><td align='right'>{_amt(abs(amt))}</td></tr>"
    if not expense_rows:
        expense_rows = "<tr><td colspan='2'><i>(none)</i></td></tr>"

    return f"""<!DOCTYPE html>
<html><head>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 10pt; }}
  h1 {{ font-size: 13pt; text-align: center; }}
  h2 {{ font-size: 11pt; margin-top: 16px; border-bottom: 1px solid #999; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 12px; }}
  th {{ background: #ddd; text-align: left; padding: 4px 6px; }}
  td {{ padding: 3px 6px; border-bottom: 1px solid #eee; }}
</style>
</head><body>
<h1>Account Summary Report</h1>
<p style="text-align:center">Period: {report.period_label}</p>

<h2>Overview</h2>
<table>
  <tr>
    <th>Account</th><th>Type</th><th>Opening</th>
    <th>Credits</th><th>Debits</th><th>Net Change</th>
    <th>Closing</th><th>Txns</th>
  </tr>
  {rows_html}
</table>

<h2>Income by Category</h2>
<table>
  <tr><th>Category</th><th>Amount</th></tr>
  {income_rows}
</table>

<h2>Expenses by Category</h2>
<table>
  <tr><th>Category</th><th>Amount</th></tr>
  {expense_rows}
</table>
</body></html>"""
