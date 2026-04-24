"""Tests for investment service methods."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from dads_money.models import (
    AccountType,
    InvestmentTransactionType,
    SecurityType,
    TransactionStatus,
)
from dads_money.services import MoneyService
from dads_money.storage import Storage


@pytest.fixture
def service(temp_db: Path) -> MoneyService:
    svc = MoneyService(temp_db)
    yield svc  # type: ignore[misc]
    svc.close()


@pytest.fixture
def inv_account(service: MoneyService):
    return service.create_account(
        name="My Portfolio",
        account_type=AccountType.INVESTMENT,
        opening_balance=10000.0,
    )


@pytest.fixture
def aapl(service: MoneyService):
    return service.create_security(
        name="Apple Inc",
        ticker_symbol="AAPL",
        security_type=SecurityType.STOCK,
    )


# ---------------------------------------------------------------------------
# Security CRUD
# ---------------------------------------------------------------------------


def test_create_and_get_security(service: MoneyService) -> None:
    sec = service.create_security("Fund X", "FNDX", SecurityType.MUTUAL_FUND)
    fetched = service.get_security(sec.id)
    assert fetched is not None
    assert fetched.name == "Fund X"
    assert fetched.ticker_symbol == "FNDX"
    assert fetched.security_type == SecurityType.MUTUAL_FUND


def test_get_all_securities_sorted(service: MoneyService) -> None:
    service.create_security("Zeta Corp", "Z")
    service.create_security("Alpha Corp", "A")
    all_secs = service.get_all_securities()
    assert all_secs[0].name == "Alpha Corp"
    assert all_secs[1].name == "Zeta Corp"


def test_update_security(service: MoneyService) -> None:
    sec = service.create_security("Old Name", "OLD")
    sec.name = "New Name"
    service.update_security(sec)
    fetched = service.get_security(sec.id)
    assert fetched is not None
    assert fetched.name == "New Name"


def test_delete_security(service: MoneyService) -> None:
    sec = service.create_security("To Delete", "DEL")
    service.delete_security(sec.id)
    assert service.get_security(sec.id) is None


# ---------------------------------------------------------------------------
# Security prices
# ---------------------------------------------------------------------------


def test_add_and_get_latest_price(service: MoneyService, aapl) -> None:
    service.add_security_price(aapl.id, date(2026, 1, 1), Decimal("150"))
    service.add_security_price(aapl.id, date(2026, 3, 1), Decimal("175"))
    latest = service.get_latest_price(aapl.id)
    assert latest is not None
    assert latest.price == Decimal("175")


def test_upsert_price_same_date(service: MoneyService, aapl) -> None:
    service.add_security_price(aapl.id, date(2026, 1, 1), Decimal("100"))
    service.add_security_price(aapl.id, date(2026, 1, 1), Decimal("105"))  # update
    history = service.get_price_history(aapl.id)
    assert len(history) == 1
    assert history[0].price == Decimal("105")


def test_price_history_order(service: MoneyService, aapl) -> None:
    service.add_security_price(aapl.id, date(2026, 3, 1), Decimal("175"))
    service.add_security_price(aapl.id, date(2026, 1, 1), Decimal("150"))
    history = service.get_price_history(aapl.id)
    assert history[0].date < history[1].date


# ---------------------------------------------------------------------------
# Investment transactions
# ---------------------------------------------------------------------------


def test_create_buy_transaction(service: MoneyService, inv_account, aapl) -> None:
    txn = service.create_investment_transaction(
        account_id=inv_account.id,
        transaction_type=InvestmentTransactionType.BUY,
        txn_date=date(2026, 1, 10),
        security_id=aapl.id,
        quantity=Decimal("100"),
        price=Decimal("1.50"),
        commission=Decimal("5"),
    )
    assert txn.amount == Decimal("-155")  # -(100*1.50 + 5)
    fetched = service.get_investment_transaction(txn.id)
    assert fetched is not None
    assert fetched.quantity == Decimal("100")


def test_buy_reduces_account_cash(service: MoneyService, inv_account, aapl) -> None:
    opening = inv_account.opening_balance
    service.create_investment_transaction(
        account_id=inv_account.id,
        transaction_type=InvestmentTransactionType.BUY,
        txn_date=date(2026, 1, 10),
        security_id=aapl.id,
        quantity=Decimal("100"),
        price=Decimal("1.50"),
        commission=Decimal("5"),
    )
    acct = service.get_account(inv_account.id)
    assert acct is not None
    assert acct.current_balance == opening + Decimal("-155")


def test_delete_investment_transaction(service: MoneyService, inv_account, aapl) -> None:
    txn = service.create_investment_transaction(
        account_id=inv_account.id,
        transaction_type=InvestmentTransactionType.BUY,
        txn_date=date(2026, 1, 10),
        security_id=aapl.id,
        quantity=Decimal("100"),
        price=Decimal("1.50"),
        commission=Decimal("5"),
    )
    opening = inv_account.opening_balance
    service.delete_investment_transaction(txn.id, inv_account.id)
    assert service.get_investment_transaction(txn.id) is None
    acct = service.get_account(inv_account.id)
    assert acct is not None
    assert acct.current_balance == opening


# ---------------------------------------------------------------------------
# Holdings computation
# ---------------------------------------------------------------------------


def test_holdings_after_buy(service: MoneyService, inv_account, aapl) -> None:
    service.create_investment_transaction(
        account_id=inv_account.id,
        transaction_type=InvestmentTransactionType.BUY,
        txn_date=date(2026, 1, 10),
        security_id=aapl.id,
        quantity=Decimal("100"),
        price=Decimal("1.50"),
        commission=Decimal("5"),
    )
    holdings = service.get_holdings_for_account(inv_account.id)
    assert len(holdings) == 1
    h = holdings[0]
    assert h.shares == Decimal("100")
    assert h.total_cost == Decimal("155")  # 100*1.50 + 5
    assert h.avg_cost == Decimal("1.55")


def test_holdings_after_partial_sell(service: MoneyService, inv_account, aapl) -> None:
    service.create_investment_transaction(
        account_id=inv_account.id,
        transaction_type=InvestmentTransactionType.BUY,
        txn_date=date(2026, 1, 10),
        security_id=aapl.id,
        quantity=Decimal("100"),
        price=Decimal("1.50"),
        commission=Decimal("5"),
    )
    service.create_investment_transaction(
        account_id=inv_account.id,
        transaction_type=InvestmentTransactionType.SELL,
        txn_date=date(2026, 2, 1),
        security_id=aapl.id,
        quantity=Decimal("40"),
        price=Decimal("2.00"),
        commission=Decimal("5"),
    )
    holdings = service.get_holdings_for_account(inv_account.id)
    assert len(holdings) == 1
    h = holdings[0]
    assert h.shares == Decimal("60")


def test_holdings_zero_after_full_sell(service: MoneyService, inv_account, aapl) -> None:
    service.create_investment_transaction(
        account_id=inv_account.id,
        transaction_type=InvestmentTransactionType.BUY,
        txn_date=date(2026, 1, 10),
        security_id=aapl.id,
        quantity=Decimal("100"),
        price=Decimal("1.50"),
        commission=Decimal("5"),
    )
    service.create_investment_transaction(
        account_id=inv_account.id,
        transaction_type=InvestmentTransactionType.SELL,
        txn_date=date(2026, 2, 1),
        security_id=aapl.id,
        quantity=Decimal("100"),
        price=Decimal("2.00"),
        commission=Decimal("5"),
    )
    holdings = service.get_holdings_for_account(inv_account.id)
    assert len(holdings) == 0


def test_holdings_market_value(service: MoneyService, inv_account, aapl) -> None:
    service.create_investment_transaction(
        account_id=inv_account.id,
        transaction_type=InvestmentTransactionType.BUY,
        txn_date=date(2026, 1, 10),
        security_id=aapl.id,
        quantity=Decimal("100"),
        price=Decimal("1.50"),
        commission=Decimal("5"),
    )
    service.add_security_price(aapl.id, date(2026, 3, 1), Decimal("2.00"))
    holdings = service.get_holdings_for_account(inv_account.id)
    h = holdings[0]
    assert h.current_price == Decimal("2.00")
    assert h.market_value == Decimal("200")
    assert h.gain_loss == Decimal("200") - Decimal("155")


# ---------------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------------


def test_portfolio_summary_with_prices(service: MoneyService, inv_account, aapl) -> None:
    service.create_investment_transaction(
        account_id=inv_account.id,
        transaction_type=InvestmentTransactionType.BUY,
        txn_date=date(2026, 1, 10),
        security_id=aapl.id,
        quantity=Decimal("100"),
        price=Decimal("1.50"),
        commission=Decimal("5"),
    )
    service.add_security_price(aapl.id, date(2026, 3, 1), Decimal("2.00"))

    summary = service.get_portfolio_summary(inv_account.id)
    assert summary.holdings_value == Decimal("200")
    assert summary.cash_balance == Decimal("10000") - Decimal("155")
    assert summary.total_value is not None


def test_portfolio_summary_no_prices(service: MoneyService, inv_account, aapl) -> None:
    service.create_investment_transaction(
        account_id=inv_account.id,
        transaction_type=InvestmentTransactionType.BUY,
        txn_date=date(2026, 1, 10),
        security_id=aapl.id,
        quantity=Decimal("100"),
        price=Decimal("1.50"),
        commission=Decimal("5"),
    )
    summary = service.get_portfolio_summary(inv_account.id)
    assert summary.holdings_value is None
    assert summary.total_value is None


# ---------------------------------------------------------------------------
# QIF investment import — linked bank account synthesis
# ---------------------------------------------------------------------------


def _write_qif(path: Path, content: str) -> str:
    path.write_text(content)
    return str(path)


def test_buyx_creates_bank_debit(service: MoneyService, tmp_path: Path) -> None:
    """BuyX in investment QIF creates a matching debit in the linked bank account."""
    bank = service.create_account("ZZZ Halifax plc DG & C", AccountType.CHECKING)
    inv = service.create_account("My ISA", AccountType.INVESTMENT)

    qif = _write_qif(
        tmp_path / "inv.qif",
        "!Type:Invst\n"
        "D5/6/1999\n"
        "T448.07\n"
        "L[ZZZ Halifax plc DG & C]\n"
        "$448.07\n"
        "NBuyX\n"
        "YLLoydsTSB Ord. Shares\n"
        "I1.255098\n"
        "Q357\n"
        "O\n"
        "^\n",
    )

    service.import_qif(qif, inv.id)

    bank_txns = service.get_transactions_for_account(bank.id)
    assert len(bank_txns) == 1
    assert bank_txns[0].amount == Decimal("-448.07")
    assert bank_txns[0].payee == "LLoydsTSB Ord. Shares"


def test_sellx_creates_bank_credit(service: MoneyService, tmp_path: Path) -> None:
    """SellX in investment QIF creates a matching credit in the linked bank account."""
    bank = service.create_account("Current Account", AccountType.CHECKING)
    inv = service.create_account("Stocks ISA", AccountType.INVESTMENT)

    qif = _write_qif(
        tmp_path / "sell.qif",
        "!Type:Invst\n"
        "D1/15/2000\n"
        "T500.00\n"
        "L[Current Account]\n"
        "$500.00\n"
        "NSellX\n"
        "YAcme Corp\n"
        "I5.00\n"
        "Q100\n"
        "O\n"
        "^\n",
    )

    service.import_qif(qif, inv.id)

    bank_txns = service.get_transactions_for_account(bank.id)
    assert len(bank_txns) == 1
    assert bank_txns[0].amount == Decimal("500.00")


def test_buyx_no_linked_account_skips_bank(service: MoneyService, tmp_path: Path) -> None:
    """BuyX with an unknown linked account does not raise; bank entry is skipped."""
    inv = service.create_account("My ISA", AccountType.INVESTMENT)

    qif = _write_qif(
        tmp_path / "inv.qif",
        "!Type:Invst\n"
        "D5/6/1999\n"
        "T448.07\n"
        "L[NonExistentBank]\n"
        "$448.07\n"
        "NBuyX\n"
        "YSome Share\n"
        "I1.00\n"
        "Q100\n"
        "O\n"
        "^\n",
    )

    count = service.import_qif(qif, inv.id)
    # Only the investment transaction is counted; no bank transaction
    assert count == 1


def test_buyx_bank_debit_not_duplicated(service: MoneyService, tmp_path: Path) -> None:
    """Re-importing the same QIF does not add duplicate bank entries."""
    bank = service.create_account("ZZZ Halifax plc DG & C", AccountType.CHECKING)
    inv = service.create_account("My ISA", AccountType.INVESTMENT)

    content = (
        "!Type:Invst\n"
        "D5/6/1999\n"
        "T448.07\n"
        "L[ZZZ Halifax plc DG & C]\n"
        "$448.07\n"
        "NBuyX\n"
        "YLLoydsTSB Ord. Shares\n"
        "I1.255098\n"
        "Q357\n"
        "O\n"
        "^\n"
    )
    qif = _write_qif(tmp_path / "inv.qif", content)

    service.import_qif(qif, inv.id)
    service.import_qif(qif, inv.id)

    bank_txns = service.get_transactions_for_account(bank.id)
    assert len(bank_txns) == 1
