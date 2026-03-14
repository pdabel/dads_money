"""Integration tests: investment account full round-trip."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from dads_money.models import AccountType, InvestmentTransactionType, SecurityType
from dads_money.services import MoneyService


@pytest.fixture
def service(temp_db: Path) -> MoneyService:
    svc = MoneyService(temp_db)
    yield svc  # type: ignore[misc]
    svc.close()


def test_full_buy_sell_dividend_roundtrip(service: MoneyService) -> None:
    """Buy, partially sell, receive dividend; verify holdings, cash, and summary."""

    # ---- Set up account and security ----
    acct = service.create_account("Test Portfolio", AccountType.INVESTMENT, opening_balance=5000.0)
    sec = service.create_security("Widget Corp", "WDGT", SecurityType.STOCK)

    # ---- Buy 200 shares at £10, commission £10 ----
    service.create_investment_transaction(
        account_id=acct.id,
        transaction_type=InvestmentTransactionType.BUY,
        txn_date=date(2025, 6, 1),
        security_id=sec.id,
        quantity=Decimal("200"),
        price=Decimal("10"),
        commission=Decimal("10"),
    )

    acct_after_buy = service.get_account(acct.id)
    assert acct_after_buy is not None
    # cash = 5000 - (200*10 + 10) = 5000 - 2010 = 2990
    assert acct_after_buy.current_balance == Decimal("2990")

    # ---- Holdings: 200 shares, avg cost £10.05 ----
    holdings = service.get_holdings_for_account(acct.id)
    assert len(holdings) == 1
    h = holdings[0]
    assert h.shares == Decimal("200")
    assert h.total_cost == Decimal("2010")
    assert h.avg_cost == Decimal("10.05")

    # ---- Sell 100 shares at £12, commission £10 ----
    service.create_investment_transaction(
        account_id=acct.id,
        transaction_type=InvestmentTransactionType.SELL,
        txn_date=date(2025, 9, 1),
        security_id=sec.id,
        quantity=Decimal("100"),
        price=Decimal("12"),
        commission=Decimal("10"),
    )

    acct_after_sell = service.get_account(acct.id)
    assert acct_after_sell is not None
    # cash = 2990 + (100*12 - 10) = 2990 + 1190 = 4180
    assert acct_after_sell.current_balance == Decimal("4180")

    holdings2 = service.get_holdings_for_account(acct.id)
    assert len(holdings2) == 1
    assert holdings2[0].shares == Decimal("100")

    # ---- Receive dividend £50 ----
    service.create_investment_transaction(
        account_id=acct.id,
        transaction_type=InvestmentTransactionType.DIV,
        txn_date=date(2025, 12, 1),
        security_id=sec.id,
        quantity=Decimal("0"),
        price=Decimal("50"),  # amount field for income types
    )

    acct_after_div = service.get_account(acct.id)
    assert acct_after_div is not None
    # cash = 4180 + 50 = 4230
    assert acct_after_div.current_balance == Decimal("4230")

    # Holdings unchanged by dividend
    holdings3 = service.get_holdings_for_account(acct.id)
    assert len(holdings3) == 1
    assert holdings3[0].shares == Decimal("100")

    # ---- Add price and check portfolio summary ----
    service.add_security_price(sec.id, date(2026, 1, 1), Decimal("14"))
    summary = service.get_portfolio_summary(acct.id)
    assert summary.cash_balance == Decimal("4230")
    assert summary.holdings_value == Decimal("1400")  # 100 * 14
    assert summary.total_value == Decimal("5630")  # 4230 + 1400
    assert summary.unrealized_gain_loss is not None

    # ---- Transactions list ----
    txns = service.get_investment_transactions_for_account(acct.id)
    assert len(txns) == 3


def test_migrate_schema_creates_investment_tables(service: MoneyService) -> None:
    """Verify investment tables exist after schema migration."""
    storage = service.storage
    cursor = storage.conn.cursor()
    tables = {
        row[0]
        for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert "securities" in tables
    assert "security_prices" in tables
    assert "investment_transactions" in tables
