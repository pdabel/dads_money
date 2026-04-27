"""UK Tax Report dialog."""

from datetime import date as Date
from pathlib import Path
from typing import Any, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPageLayout, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import Account, AccountType, SavingsAccountType, UKTaxReport
from ..services import MoneyService
from ..settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ISA_SUBTYPES = {SavingsAccountType.CASH_ISA, SavingsAccountType.STOCKS_SHARES_ISA}

_CURRENT_TAX_YEAR_START: int = (
    Date.today().year - 1
    if Date.today().month < 4 or (Date.today().month == 4 and Date.today().day < 6)
    else Date.today().year
)


def _tax_year_label(year_start: int) -> str:
    return f"{year_start}/{str(year_start + 1)[-2:]}"


# ---------------------------------------------------------------------------
# Account selection widget
# ---------------------------------------------------------------------------


class _AccountSelector(QWidget):
    """Scrollable list of checkboxes — one per account."""

    def __init__(self, accounts: List[Account], parent: Any = None) -> None:
        super().__init__(parent)
        self._checkboxes: List[tuple[Account, QCheckBox]] = []

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Select-all / none buttons
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
            is_isa = account.savings_subtype in _ISA_SUBTYPES
            label = account.name
            if account.owner:
                label += f"  [{account.owner}]"
            if is_isa:
                label += "  [ISA – exempt]"
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

    def select_for_owner(self, owner: str) -> None:
        """Check only accounts for *owner* plus all Joint accounts.

        If *owner* is empty-string (meaning "All"), all accounts are checked.
        Joint accounts are identified by ``account.owner.strip().lower() == "joint"``.
        """
        if not owner:
            self._select_all()
            return
        for account, cb in self._checkboxes:
            acct_owner = account.owner.strip()
            is_joint = acct_owner.lower() == "joint"
            cb.setChecked(acct_owner == owner or is_joint)

    def selected_account_ids(self) -> List[str]:
        return [acc.id for acc, cb in self._checkboxes if cb.isChecked()]

    def joint_account_ids_from_selection(self) -> List[str]:
        """Return IDs of checked accounts that are tagged as Joint."""
        return [
            acc.id
            for acc, cb in self._checkboxes
            if cb.isChecked() and acc.owner.strip().lower() == "joint"
        ]


# ---------------------------------------------------------------------------
# Report results widget
# ---------------------------------------------------------------------------


def _make_header_label(text: str) -> QLabel:
    lbl = QLabel(text)
    font = QFont()
    font.setBold(True)
    font.setPointSize(11)
    lbl.setFont(font)
    return lbl


def _make_amount_item(amount: object, *, exempt: bool = False) -> QTableWidgetItem:
    from decimal import Decimal

    val = Decimal(str(amount))
    item = QTableWidgetItem(f"£{val:,.2f}")
    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[attr-defined]
    if exempt:
        item.setForeground(Qt.gray)  # type: ignore[attr-defined]
    return item


def _make_share_item(share_pct: int) -> QTableWidgetItem:
    """Return a table cell showing the joint share percentage, or blank for 100%."""
    if share_pct >= 100:
        return QTableWidgetItem("")
    item = QTableWidgetItem(f"{share_pct}% (joint)")
    item.setTextAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
    item.setForeground(Qt.darkCyan)  # type: ignore[attr-defined]
    item.setToolTip(
        f"This amount is {share_pct}% of the account total — joint account, split equally between owners."
    )
    return item


class _ReportResultsWidget(QWidget):
    """Displays a rendered UKTaxReport in tabbed sections."""

    def __init__(self, report: UKTaxReport, settings: Settings, parent: Any = None) -> None:
        super().__init__(parent)
        self._report = report
        self._settings = settings
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout()

        # Title
        title = _make_header_label(f"UK Tax Report — Tax Year {self._report.tax_year_label}")
        title.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        outer.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_summary_tab(), "Summary")
        tabs.addTab(self._build_cgt_tab(), "Capital Gains")
        tabs.addTab(self._build_dividends_tab(), "Dividends")
        tabs.addTab(self._build_interest_tab(), "Interest")
        tabs.addTab(self._build_other_income_tab(), "Other Income")
        outer.addWidget(tabs)

        self.setLayout(outer)

    # ----------------------------------------------------------------
    # Summary tab
    # ----------------------------------------------------------------

    def _build_summary_tab(self) -> QWidget:
        r = self._report
        w = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)

        def _row(label: str, value: str, bold: bool = False) -> QWidget:
            container = QWidget()
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label)
            val = QLabel(value)
            if bold:
                font = QFont()
                font.setBold(True)
                lbl.setFont(font)
                val.setFont(font)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(val)
            container.setLayout(row)
            return container

        from decimal import Decimal

        # CGT section
        cgt_box = QGroupBox("Capital Gains Tax")
        cgt_layout = QVBoxLayout()
        cgt_layout.addWidget(_row("Total gains (excl. ISA)", f"£{r.total_gains:,.2f}"))
        cgt_layout.addWidget(_row("Total losses (excl. ISA)", f"£{r.total_losses:,.2f}"))
        cgt_layout.addWidget(
            _row("Net capital gain / (loss)", f"£{r.net_capital_gain:,.2f}", bold=True)
        )
        isa_cgt = sum((abs(e.gain) for e in r.capital_gains if e.is_isa), Decimal("0"))
        if isa_cgt:
            cgt_layout.addWidget(
                _row("ISA disposals (exempt, not included above)", f"£{isa_cgt:,.2f}")
            )
        cgt_box.setLayout(cgt_layout)
        layout.addWidget(cgt_box)

        # Income section
        inc_box = QGroupBox("Taxable Investment Income")
        inc_layout = QVBoxLayout()
        inc_layout.addWidget(_row("Dividends (excl. ISA)", f"£{r.total_dividends:,.2f}"))
        inc_layout.addWidget(
            _row("Investment interest (excl. ISA)", f"£{r.total_investment_interest:,.2f}")
        )
        inc_layout.addWidget(
            _row("Savings interest (excl. ISA)", f"£{r.total_savings_interest:,.2f}")
        )
        inc_layout.addWidget(_row("Total interest", f"£{r.total_interest:,.2f}", bold=True))
        inc_layout.addWidget(_row("Other income", f"£{r.total_other_income:,.2f}"))
        inc_box.setLayout(inc_layout)
        layout.addWidget(inc_box)

        note = QLabel(
            "<i>Note: This report is for informational purposes only and does not "
            "constitute tax advice. Annual exemptions, allowances, and reliefs are "
            "not applied. Consult a qualified tax adviser for your Self Assessment.</i>"
        )
        note.setWordWrap(True)
        note.setTextFormat(Qt.RichText)  # type: ignore[attr-defined]
        layout.addWidget(note)

        layout.addStretch()
        w.setLayout(layout)
        return w

    # ----------------------------------------------------------------
    # Capital Gains tab
    # ----------------------------------------------------------------

    def _build_cgt_tab(self) -> QWidget:
        events = self._report.capital_gains
        cols = [
            "Date",
            "Account",
            "Security",
            "Quantity",
            "Proceeds",
            "Cost",
            "Gain / (Loss)",
            "Share",
            "Exempt",
        ]
        table = QTableWidget(len(events), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.horizontalHeader().setStretchLastSection(False)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)  # type: ignore[attr-defined]
        table.setAlternatingRowColors(True)

        fmt = self._settings.date_format
        for row, e in enumerate(events):
            table.setItem(row, 0, QTableWidgetItem(e.date.strftime(fmt)))
            table.setItem(row, 1, QTableWidgetItem(e.account_name))
            table.setItem(row, 2, QTableWidgetItem(e.security_name))
            qty_item = QTableWidgetItem(f"{e.quantity:,.6f}".rstrip("0").rstrip("."))
            qty_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)  # type: ignore[attr-defined]
            table.setItem(row, 3, qty_item)
            table.setItem(row, 4, _make_amount_item(e.proceeds, exempt=e.is_isa))
            table.setItem(row, 5, _make_amount_item(e.cost, exempt=e.is_isa))
            table.setItem(row, 6, _make_amount_item(e.gain, exempt=e.is_isa))
            table.setItem(row, 7, _make_share_item(e.share_pct))
            table.setItem(row, 8, QTableWidgetItem("Yes (ISA)" if e.is_isa else ""))

        table.resizeColumnsToContents()
        w = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(table)
        w.setLayout(layout)
        return w

    # ----------------------------------------------------------------
    # Dividends tab
    # ----------------------------------------------------------------

    def _build_dividends_tab(self) -> QWidget:
        from decimal import Decimal

        items = [
            i
            for i in self._report.investment_income
            if i.income_type in ("Dividend", "Reinvested Dividend")
        ]
        cols = ["Date", "Account", "Security", "Type", "Amount", "Share", "Exempt"]
        table = QTableWidget(len(items), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)  # type: ignore[attr-defined]
        table.setAlternatingRowColors(True)

        fmt = self._settings.date_format
        for row, i in enumerate(items):
            table.setItem(row, 0, QTableWidgetItem(i.date.strftime(fmt)))
            table.setItem(row, 1, QTableWidgetItem(i.account_name))
            table.setItem(row, 2, QTableWidgetItem(i.security_name))
            table.setItem(row, 3, QTableWidgetItem(i.income_type))
            table.setItem(row, 4, _make_amount_item(i.amount, exempt=i.is_isa))
            table.setItem(row, 5, _make_share_item(i.share_pct))
            table.setItem(row, 6, QTableWidgetItem("Yes (ISA)" if i.is_isa else ""))

        table.resizeColumnsToContents()
        w = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(table)
        w.setLayout(layout)
        return w

    # ----------------------------------------------------------------
    # Interest tab
    # ----------------------------------------------------------------

    def _build_interest_tab(self) -> QWidget:
        inv_interest = [
            i
            for i in self._report.investment_income
            if i.income_type not in ("Dividend", "Reinvested Dividend")
        ]
        sav_interest = self._report.savings_interest

        tabs = QTabWidget()

        # Investment interest sub-tab
        cols_inv = ["Date", "Account", "Security", "Type", "Amount", "Share", "Exempt"]
        t1 = QTableWidget(len(inv_interest), len(cols_inv))
        t1.setHorizontalHeaderLabels(cols_inv)
        t1.verticalHeader().setVisible(False)
        t1.setEditTriggers(QTableWidget.NoEditTriggers)  # type: ignore[attr-defined]
        t1.setAlternatingRowColors(True)
        fmt = self._settings.date_format
        for row, i in enumerate(inv_interest):
            t1.setItem(row, 0, QTableWidgetItem(i.date.strftime(fmt)))
            t1.setItem(row, 1, QTableWidgetItem(i.account_name))
            t1.setItem(row, 2, QTableWidgetItem(i.security_name))
            t1.setItem(row, 3, QTableWidgetItem(i.income_type))
            t1.setItem(row, 4, _make_amount_item(i.amount, exempt=i.is_isa))
            t1.setItem(row, 5, _make_share_item(i.share_pct))
            t1.setItem(row, 6, QTableWidgetItem("Yes (ISA)" if i.is_isa else ""))
        t1.resizeColumnsToContents()
        w1 = QWidget()
        l1 = QVBoxLayout()
        l1.addWidget(t1)
        w1.setLayout(l1)
        tabs.addTab(w1, "Investment Interest")

        # Savings interest sub-tab
        cols_sav = ["Date", "Account", "Payee", "Amount", "Share", "Exempt"]
        t2 = QTableWidget(len(sav_interest), len(cols_sav))
        t2.setHorizontalHeaderLabels(cols_sav)
        t2.verticalHeader().setVisible(False)
        t2.setEditTriggers(QTableWidget.NoEditTriggers)  # type: ignore[attr-defined]
        t2.setAlternatingRowColors(True)
        for row, i in enumerate(sav_interest):
            t2.setItem(row, 0, QTableWidgetItem(i.date.strftime(fmt)))
            t2.setItem(row, 1, QTableWidgetItem(i.account_name))
            t2.setItem(row, 2, QTableWidgetItem(i.payee))
            t2.setItem(row, 3, _make_amount_item(i.amount, exempt=i.is_isa))
            t2.setItem(row, 4, _make_share_item(i.share_pct))
            t2.setItem(row, 5, QTableWidgetItem("Yes (ISA)" if i.is_isa else ""))
        t2.resizeColumnsToContents()
        w2 = QWidget()
        l2 = QVBoxLayout()
        l2.addWidget(t2)
        w2.setLayout(l2)
        tabs.addTab(w2, "Savings Interest")

        outer = QWidget()
        outer_layout = QVBoxLayout()
        outer_layout.addWidget(tabs)
        outer.setLayout(outer_layout)
        return outer

    # ----------------------------------------------------------------
    # Other Income tab
    # ----------------------------------------------------------------

    def _build_other_income_tab(self) -> QWidget:
        items = self._report.other_income
        cols = ["Date", "Account", "Payee", "Category", "Amount", "Share"]
        table = QTableWidget(len(items), len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)  # type: ignore[attr-defined]
        table.setAlternatingRowColors(True)

        fmt = self._settings.date_format
        for row, i in enumerate(items):
            table.setItem(row, 0, QTableWidgetItem(i.date.strftime(fmt)))
            table.setItem(row, 1, QTableWidgetItem(i.account_name))
            table.setItem(row, 2, QTableWidgetItem(i.payee))
            table.setItem(row, 3, QTableWidgetItem(i.category_name))
            table.setItem(row, 4, _make_amount_item(i.amount))
            table.setItem(row, 5, _make_share_item(i.share_pct))

        table.resizeColumnsToContents()
        w = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(table)
        w.setLayout(layout)
        return w


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------


class TaxReportDialog(QDialog):
    """Dialog for generating a UK income / capital gains tax report."""

    def __init__(self, parent: Any, service: MoneyService, settings: Settings) -> None:
        super().__init__(parent)
        self.service = service
        self.settings = settings
        self._report: Optional[UKTaxReport] = None
        self._init_ui()

    def _init_ui(self) -> None:
        self.setWindowTitle("UK Tax Report")
        self.setModal(True)
        self.setMinimumSize(900, 620)

        outer = QVBoxLayout()

        # ---- options row ----
        options_box = QGroupBox("Report Options")
        opt_layout = QHBoxLayout()

        opt_layout.addWidget(QLabel("Tax Year:"))
        self._year_combo = QComboBox()
        current_year = _CURRENT_TAX_YEAR_START
        for y in range(current_year, current_year - 10, -1):
            self._year_combo.addItem(_tax_year_label(y), y)
        opt_layout.addWidget(self._year_combo)
        opt_layout.addStretch()

        generate_btn = QPushButton("Generate Report")
        generate_btn.clicked.connect(self._generate)
        generate_btn.setDefault(True)
        opt_layout.addWidget(generate_btn)

        export_btn = QPushButton("Export to Text…")
        export_btn.clicked.connect(self._export_text)
        opt_layout.addWidget(export_btn)

        print_preview_btn = QPushButton("Print Preview…")
        print_preview_btn.clicked.connect(self._print_preview)
        opt_layout.addWidget(print_preview_btn)

        print_btn = QPushButton("Print…")
        print_btn.clicked.connect(self._print_report)
        opt_layout.addWidget(print_btn)

        options_box.setLayout(opt_layout)
        outer.addWidget(options_box)

        # ---- splitter: accounts on left, results on right ----
        splitter = QSplitter(Qt.Horizontal)  # type: ignore[attr-defined]

        # Account selector
        accounts = self.service.get_all_accounts(include_closed=False, include_hidden=False)
        acct_group = QGroupBox("Include Accounts")
        acct_layout = QVBoxLayout()

        # Owner filter combo
        owner_filter_row = QHBoxLayout()
        owner_filter_row.addWidget(QLabel("Owner:"))
        self._owner_combo = QComboBox()
        self._owner_combo.setToolTip(
            "Filter accounts by owner. 'All Owners' includes every account.\n"
            "Selecting a specific owner auto-selects their accounts plus any\n"
            "accounts tagged 'Joint' (joint amounts are split 50/50)."
        )
        self._owner_combo.addItem("All Owners", "")
        distinct_owners = sorted(
            {
                a.owner.strip()
                for a in accounts
                if a.owner.strip() and a.owner.strip().lower() != "joint"
            }
        )
        for owner in distinct_owners:
            self._owner_combo.addItem(owner, owner)
        self._owner_combo.currentIndexChanged.connect(self._on_owner_filter_changed)
        owner_filter_row.addWidget(self._owner_combo)
        owner_filter_row.addStretch()
        acct_layout.addLayout(owner_filter_row)

        self._account_selector = _AccountSelector(accounts)
        acct_layout.addWidget(self._account_selector)
        acct_group.setLayout(acct_layout)
        acct_group.setMinimumWidth(260)
        splitter.addWidget(acct_group)

        # Results area (placeholder until report is generated)
        self._results_container = QWidget()
        results_layout = QVBoxLayout()
        self._placeholder_label = QLabel(
            'Select accounts and a tax year, then click "Generate Report".'
        )
        self._placeholder_label.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        self._placeholder_label.setWordWrap(True)
        results_layout.addWidget(self._placeholder_label)
        self._results_container.setLayout(results_layout)
        splitter.addWidget(self._results_container)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        outer.addWidget(splitter)

        # ---- close button ----
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)  # type: ignore[attr-defined]
        btn_box.rejected.connect(self.reject)
        outer.addWidget(btn_box)

        self.setLayout(outer)

    # ----------------------------------------------------------------
    # Actions
    # ----------------------------------------------------------------

    def _on_owner_filter_changed(self) -> None:
        owner = self._owner_combo.currentData() or ""
        self._account_selector.select_for_owner(owner)

    def _generate(self) -> None:
        account_ids = self._account_selector.selected_account_ids()
        if not account_ids:
            QMessageBox.warning(self, "No Accounts", "Please select at least one account.")
            return

        joint_ids = self._account_selector.joint_account_ids_from_selection()
        # Only apply 50/50 split when a specific owner is selected (not "All Owners")
        owner_filter = self._owner_combo.currentData() or ""
        effective_joint_ids = joint_ids if owner_filter else []

        tax_year_start: int = self._year_combo.currentData()
        try:
            report = self.service.generate_uk_tax_report(
                tax_year_start, account_ids, joint_account_ids=effective_joint_ids or None
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to generate report:\n{exc}")
            return

        self._report = report
        self._show_results(report)

    def _show_results(self, report: UKTaxReport) -> None:
        """Replace the results container contents with the rendered report."""
        layout = self._results_container.layout()
        if layout is None:
            return

        # Remove old widgets
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        results_widget = _ReportResultsWidget(report, self.settings, self._results_container)
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

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Tax Report",
            str(Path.home() / f"tax_report_{self._report.tax_year_label.replace('/', '-')}.txt"),
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


def _render_report_as_text(report: UKTaxReport, settings: Settings) -> str:
    lines: List[str] = []
    fmt = settings.date_format

    def _section(title: str) -> None:
        lines.append("")
        lines.append("=" * 70)
        lines.append(f"  {title}")
        lines.append("=" * 70)

    def _row(*cols: str, widths: Optional[List[int]] = None) -> str:
        if widths:
            return "  ".join(str(c).ljust(w) for c, w in zip(cols, widths))
        return "  ".join(cols)

    lines.append(f"UK TAX REPORT — TAX YEAR {report.tax_year_label}")
    lines.append(f"Generated: {Date.today().strftime(fmt)}")
    lines.append("")

    # ---- Summary ----
    _section("SUMMARY")
    lines.append(f"  Net Capital Gain / (Loss):   £{report.net_capital_gain:>12,.2f}")
    lines.append(f"  Total Dividends:             £{report.total_dividends:>12,.2f}")
    lines.append(f"  Total Interest:              £{report.total_interest:>12,.2f}")
    lines.append(f"  Other Income:                £{report.total_other_income:>12,.2f}")
    lines.append("")
    lines.append("  NOTE: Annual exemptions, allowances and reliefs are NOT applied.")
    lines.append("  ISA income and gains are shown separately and are tax-free.")

    # ---- Capital Gains ----
    _section("CAPITAL GAINS / LOSSES")
    if report.capital_gains:
        w = [12, 20, 24, 10, 12, 12, 14, 8, 10]
        lines.append(
            _row(
                "Date",
                "Account",
                "Security",
                "Qty",
                "Proceeds",
                "Cost",
                "Gain/(Loss)",
                "Share",
                "Exempt",
                widths=w,
            )
        )
        lines.append("-" * 130)
        for e in report.capital_gains:
            lines.append(
                _row(
                    e.date.strftime(fmt),
                    e.account_name[:18],
                    e.security_name[:22],
                    f"{e.quantity:,.4f}",
                    f"£{e.proceeds:,.2f}",
                    f"£{e.cost:,.2f}",
                    f"£{e.gain:,.2f}",
                    f"{e.share_pct}%" if e.share_pct < 100 else "",
                    "ISA" if e.is_isa else "",
                    widths=w,
                )
            )
        lines.append("-" * 130)
        lines.append(
            f"  Total Gains:  £{report.total_gains:>12,.2f}    Total Losses: £{report.total_losses:>12,.2f}"
        )
        lines.append(f"  Net:          £{report.net_capital_gain:>12,.2f}")
    else:
        lines.append("  No disposals recorded in this tax year.")

    # ---- Dividends ----
    _section("DIVIDENDS")
    divs = [
        i for i in report.investment_income if i.income_type in ("Dividend", "Reinvested Dividend")
    ]
    if divs:
        w = [12, 20, 24, 20, 12, 8, 10]
        lines.append(
            _row("Date", "Account", "Security", "Type", "Amount", "Share", "Exempt", widths=w)
        )
        lines.append("-" * 110)
        for i in divs:
            lines.append(
                _row(
                    i.date.strftime(fmt),
                    i.account_name[:18],
                    i.security_name[:22],
                    i.income_type[:18],
                    f"£{i.amount:,.2f}",
                    f"{i.share_pct}%" if i.share_pct < 100 else "",
                    "ISA" if i.is_isa else "",
                    widths=w,
                )
            )
        lines.append("-" * 110)
        lines.append(f"  Total Dividends (excl. ISA): £{report.total_dividends:>12,.2f}")
    else:
        lines.append("  No dividend income recorded in this tax year.")

    # ---- Interest ----
    _section("INTEREST")
    inv_int = [
        i
        for i in report.investment_income
        if i.income_type not in ("Dividend", "Reinvested Dividend")
    ]
    sav_int = report.savings_interest
    if inv_int or sav_int:
        w = [12, 20, 24, 12, 8, 10]
        lines.append(_row("Date", "Account", "Description", "Amount", "Share", "Exempt", widths=w))
        lines.append("-" * 90)
        for i in inv_int:
            desc = f"{i.income_type}: {i.security_name}" if i.security_name else i.income_type
            lines.append(
                _row(
                    i.date.strftime(fmt),
                    i.account_name[:18],
                    desc[:22],
                    f"£{i.amount:,.2f}",
                    f"{i.share_pct}%" if i.share_pct < 100 else "",
                    "ISA" if i.is_isa else "",
                    widths=w,
                )
            )
        for i in sav_int:
            lines.append(
                _row(
                    i.date.strftime(fmt),
                    i.account_name[:18],
                    (i.payee or "Savings Interest")[:22],
                    f"£{i.amount:,.2f}",
                    f"{i.share_pct}%" if i.share_pct < 100 else "",
                    "ISA" if i.is_isa else "",
                    widths=w,
                )
            )
        lines.append("-" * 90)
        lines.append(f"  Total Interest (excl. ISA): £{report.total_interest:>12,.2f}")
    else:
        lines.append("  No interest income recorded in this tax year.")

    # ---- Other Income ----
    _section("OTHER INCOME")
    if report.other_income:
        w = [12, 20, 20, 20, 12, 8]
        lines.append(_row("Date", "Account", "Payee", "Category", "Amount", "Share", widths=w))
        lines.append("-" * 100)
        for i in report.other_income:
            lines.append(
                _row(
                    i.date.strftime(fmt),
                    i.account_name[:18],
                    i.payee[:18],
                    i.category_name[:18],
                    f"£{i.amount:,.2f}",
                    f"{i.share_pct}%" if i.share_pct < 100 else "",
                    widths=w,
                )
            )
        lines.append("-" * 100)
        lines.append(f"  Total Other Income: £{report.total_other_income:>12,.2f}")
    else:
        lines.append("  No other income recorded in this tax year.")

    lines.append("")
    lines.append("=" * 70)
    lines.append("  END OF REPORT")
    lines.append("=" * 70)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML renderer (used for printing)
# ---------------------------------------------------------------------------


def _render_report_as_html(report: UKTaxReport, settings: Settings) -> str:
    fmt = settings.date_format

    def _th(*headers: str) -> str:
        return "".join(f"<th>{h}</th>" for h in headers)

    def _td(*cells: str, right: bool = False) -> str:
        align = ' style="text-align:right"' if right else ""
        return "".join(f"<td{align}>{c}</td>" for c in cells)

    def _amount(val: object, *, exempt: bool = False) -> str:
        from decimal import Decimal

        v = Decimal(str(val))
        txt = f"£{v:,.2f}"
        if exempt:
            return f'<span style="color:#888">{txt}</span>'
        return txt

    css = """
    <style>
      body { font-family: Arial, sans-serif; font-size: 9pt; color: #000; }
      h1   { font-size: 13pt; text-align: center; margin-bottom: 4px; }
      h2   { font-size: 10pt; border-bottom: 1px solid #000; margin-top: 14px; }
      table { border-collapse: collapse; width: 100%; margin-top: 6px; font-size: 8pt; }
      th   { background: #333; color: #fff; padding: 3px 6px; text-align: left; }
      td   { padding: 2px 6px; border-bottom: 1px solid #ddd; }
      tr:nth-child(even) td { background: #f5f5f5; }
      .total-row td { font-weight: bold; border-top: 1px solid #000; background: #eef; }
      .note { font-size: 8pt; font-style: italic; color: #555; margin-top: 8px; }
      .summary-table td:last-child { text-align: right; }
      .joint { color: #007070; font-style: italic; text-align: center; }
    </style>
    """

    html_parts: List[str] = [css]
    html_parts.append(f"<h1>UK Tax Report &mdash; Tax Year {report.tax_year_label}</h1>")
    html_parts.append(
        f'<p style="text-align:center;font-size:8pt">Generated: {Date.today().strftime(fmt)}</p>'
    )

    # ---- Summary ----
    html_parts.append("<h2>Summary</h2>")
    html_parts.append('<table class="summary-table" style="width:40%">')
    rows = [
        ("Net Capital Gain / (Loss)", f"£{report.net_capital_gain:,.2f}"),
        ("Total Dividends (excl. ISA)", f"£{report.total_dividends:,.2f}"),
        ("Total Interest (excl. ISA)", f"£{report.total_interest:,.2f}"),
        ("Other Income", f"£{report.total_other_income:,.2f}"),
    ]
    for label, val in rows:
        html_parts.append(
            f"<tr><td><b>{label}</b></td><td style='text-align:right'>{val}</td></tr>"
        )
    html_parts.append("</table>")
    html_parts.append(
        '<p class="note">Annual exemptions, allowances, and reliefs are NOT applied. '
        "ISA income and gains are shown separately and are tax-free. "
        "This report does not constitute tax advice.</p>"
    )

    # ---- Capital Gains ----
    html_parts.append("<h2>Capital Gains / Losses</h2>")
    if report.capital_gains:
        html_parts.append("<table>")
        html_parts.append(
            f"<tr>{_th('Date','Account','Security','Qty','Proceeds','Cost','Gain/(Loss)','Share','Exempt')}</tr>"
        )
        for e in report.capital_gains:
            share_cell = (
                f"<td class='joint'>{e.share_pct}%</td>" if e.share_pct < 100 else "<td></td>"
            )
            html_parts.append(
                f"<tr>{_td(e.date.strftime(fmt), e.account_name, e.security_name)}"
                f"{_td(f'{e.quantity:,.4f}', right=True)}"
                f"<td style='text-align:right'>{_amount(e.proceeds, exempt=e.is_isa)}</td>"
                f"<td style='text-align:right'>{_amount(e.cost, exempt=e.is_isa)}</td>"
                f"<td style='text-align:right'>{_amount(e.gain, exempt=e.is_isa)}</td>"
                f"{share_cell}{_td('ISA' if e.is_isa else '')}</tr>"
            )
        html_parts.append(
            f'<tr class="total-row"><td colspan="4">Totals (excl. ISA)</td>'
            f"<td></td><td></td>"
            f"<td style='text-align:right'>Gains: £{report.total_gains:,.2f} &nbsp; Losses: £{report.total_losses:,.2f} &nbsp; Net: £{report.net_capital_gain:,.2f}</td>"
            f"<td></td><td></td></tr>"
        )
        html_parts.append("</table>")
    else:
        html_parts.append("<p>No disposals recorded in this tax year.</p>")

    # ---- Dividends ----
    divs = [
        i for i in report.investment_income if i.income_type in ("Dividend", "Reinvested Dividend")
    ]
    html_parts.append("<h2>Dividends</h2>")
    if divs:
        html_parts.append("<table>")
        html_parts.append(
            f"<tr>{_th('Date','Account','Security','Type','Amount','Share','Exempt')}</tr>"
        )
        for i in divs:
            share_cell = (
                f"<td class='joint'>{i.share_pct}%</td>" if i.share_pct < 100 else "<td></td>"
            )
            html_parts.append(
                f"<tr>{_td(i.date.strftime(fmt), i.account_name, i.security_name, i.income_type)}"
                f"<td style='text-align:right'>{_amount(i.amount, exempt=i.is_isa)}</td>"
                f"{share_cell}{_td('ISA' if i.is_isa else '')}</tr>"
            )
        html_parts.append(
            f'<tr class="total-row"><td colspan="4">Total Dividends (excl. ISA)</td>'
            f"<td style='text-align:right'>£{report.total_dividends:,.2f}</td><td></td><td></td></tr>"
        )
        html_parts.append("</table>")
    else:
        html_parts.append("<p>No dividend income recorded in this tax year.</p>")

    # ---- Interest ----
    inv_int = [
        i
        for i in report.investment_income
        if i.income_type not in ("Dividend", "Reinvested Dividend")
    ]
    sav_int = report.savings_interest
    html_parts.append("<h2>Interest</h2>")
    if inv_int or sav_int:
        html_parts.append("<table>")
        html_parts.append(
            f"<tr>{_th('Date','Account','Description','Amount','Share','Exempt')}</tr>"
        )
        for i in inv_int:
            desc = f"{i.income_type}: {i.security_name}" if i.security_name else i.income_type
            share_cell = (
                f"<td class='joint'>{i.share_pct}%</td>" if i.share_pct < 100 else "<td></td>"
            )
            html_parts.append(
                f"<tr>{_td(i.date.strftime(fmt), i.account_name, desc)}"
                f"<td style='text-align:right'>{_amount(i.amount, exempt=i.is_isa)}</td>"
                f"{share_cell}{_td('ISA' if i.is_isa else '')}</tr>"
            )
        for i in sav_int:
            desc = i.payee or "Savings Interest"
            share_cell = (
                f"<td class='joint'>{i.share_pct}%</td>" if i.share_pct < 100 else "<td></td>"
            )
            html_parts.append(
                f"<tr>{_td(i.date.strftime(fmt), i.account_name, desc)}"
                f"<td style='text-align:right'>{_amount(i.amount, exempt=i.is_isa)}</td>"
                f"{share_cell}{_td('ISA' if i.is_isa else '')}</tr>"
            )
        html_parts.append(
            f'<tr class="total-row"><td colspan="3">Total Interest (excl. ISA)</td>'
            f"<td style='text-align:right'>£{report.total_interest:,.2f}</td><td></td><td></td></tr>"
        )
        html_parts.append("</table>")
    else:
        html_parts.append("<p>No interest income recorded in this tax year.</p>")

    # ---- Other Income ----
    html_parts.append("<h2>Other Income</h2>")
    if report.other_income:
        html_parts.append("<table>")
        html_parts.append(f"<tr>{_th('Date','Account','Payee','Category','Amount','Share')}</tr>")
        for i in report.other_income:
            share_cell = (
                f"<td class='joint'>{i.share_pct}%</td>" if i.share_pct < 100 else "<td></td>"
            )
            html_parts.append(
                f"<tr>{_td(i.date.strftime(fmt), i.account_name, i.payee, i.category_name)}"
                f"<td style='text-align:right'>{_amount(i.amount)}</td>{share_cell}</tr>"
            )
        html_parts.append(
            f'<tr class="total-row"><td colspan="4">Total Other Income</td>'
            f"<td style='text-align:right'>£{report.total_other_income:,.2f}</td><td></td></tr>"
        )
        html_parts.append("</table>")
    else:
        html_parts.append("<p>No other income recorded in this tax year.</p>")

    return "".join(html_parts)
