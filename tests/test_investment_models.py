"""Tests for investment data models and XIRR calculation."""

from datetime import date
from decimal import Decimal

import pytest

from dads_money.models import (
    Holding,
    InvestmentTransaction,
    InvestmentTransactionType,
    PortfolioSummary,
    Security,
    SecurityPrice,
    SecurityType,
    TransactionStatus,
)
from dads_money.services import _compute_cash_amount, _xirr


# ---------------------------------------------------------------------------
# Security model
# ---------------------------------------------------------------------------


def test_security_defaults() -> None:
    sec = Security(name="Apple Inc", ticker_symbol="AAPL")
    assert sec.name == "Apple Inc"
    assert sec.ticker_symbol == "AAPL"
    assert sec.security_type == SecurityType.STOCK
    assert sec.id  # UUID generated


def test_security_price_decimal_coercion() -> None:
    sp = SecurityPrice(security_id="x", date=date(2026, 1, 1), price=1.5)  # type: ignore[arg-type]
    assert isinstance(sp.price, Decimal)
    assert sp.price == Decimal("1.5")


# ---------------------------------------------------------------------------
# InvestmentTransaction decimal coercion
# ---------------------------------------------------------------------------


def test_investment_transaction_decimal_coercion() -> None:
    txn = InvestmentTransaction(
        account_id="a",
        quantity=100,  # type: ignore[arg-type]
        price=1.50,  # type: ignore[arg-type]
        commission=5,  # type: ignore[arg-type]
        amount=-155,  # type: ignore[arg-type]
    )
    assert isinstance(txn.quantity, Decimal)
    assert isinstance(txn.price, Decimal)
    assert isinstance(txn.commission, Decimal)
    assert isinstance(txn.amount, Decimal)


# ---------------------------------------------------------------------------
# _compute_cash_amount
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "txn_type,qty,price,commission,expected",
    [
        (
            InvestmentTransactionType.BUY,
            Decimal("100"),
            Decimal("1.50"),
            Decimal("5"),
            Decimal("-155"),
        ),
        (
            InvestmentTransactionType.SELL,
            Decimal("50"),
            Decimal("2.00"),
            Decimal("5"),
            Decimal("95"),
        ),
        (InvestmentTransactionType.DIV, Decimal("0"), Decimal("10"), Decimal("0"), Decimal("10")),
        (
            InvestmentTransactionType.INT_INC,
            Decimal("0"),
            Decimal("7.50"),
            Decimal("0"),
            Decimal("7.50"),
        ),
        (InvestmentTransactionType.ADD, Decimal("10"), Decimal("0"), Decimal("0"), Decimal("0")),
        (InvestmentTransactionType.REMOVE, Decimal("5"), Decimal("0"), Decimal("0"), Decimal("0")),
        (
            InvestmentTransactionType.REINV_DIV,
            Decimal("3"),
            Decimal("1"),
            Decimal("0"),
            Decimal("0"),
        ),
        (
            InvestmentTransactionType.RETURN_CAPITAL,
            Decimal("0"),
            Decimal("20"),
            Decimal("0"),
            Decimal("20"),
        ),
        (
            InvestmentTransactionType.MISC_INC,
            Decimal("0"),
            Decimal("5"),
            Decimal("0"),
            Decimal("5"),
        ),
    ],
)
def test_compute_cash_amount(
    txn_type: InvestmentTransactionType,
    qty: Decimal,
    price: Decimal,
    commission: Decimal,
    expected: Decimal,
) -> None:
    result = _compute_cash_amount(txn_type, qty, price, commission)
    assert result == expected, f"{txn_type}: got {result}, expected {expected}"


# ---------------------------------------------------------------------------
# _xirr
# ---------------------------------------------------------------------------


def test_xirr_simple_known_rate() -> None:
    # Invest 1000 today, receive 1100 in exactly 1 year → XIRR = 10%
    flows = [
        (date(2025, 1, 1), Decimal("-1000")),
        (date(2026, 1, 1), Decimal("1100")),
    ]
    rate = _xirr(flows)
    assert rate is not None
    assert abs(rate - 0.10) < 0.001


def test_xirr_all_same_sign_returns_none() -> None:
    flows = [
        (date(2025, 1, 1), Decimal("-1000")),
        (date(2026, 1, 1), Decimal("-500")),
    ]
    assert _xirr(flows) is None


def test_xirr_insufficient_data_returns_none() -> None:
    assert _xirr([(date(2025, 1, 1), Decimal("-100"))]) is None
    assert _xirr([]) is None


# ---------------------------------------------------------------------------
# Holding dataclass
# ---------------------------------------------------------------------------


def test_holding_creation() -> None:
    sec = Security(name="Test Corp", ticker_symbol="TST")
    h = Holding(
        security=sec,
        shares=Decimal("100"),
        avg_cost=Decimal("10"),
        total_cost=Decimal("1000"),
        current_price=Decimal("12"),
        market_value=Decimal("1200"),
        gain_loss=Decimal("200"),
        gain_loss_pct=Decimal("20"),
    )
    assert h.shares == Decimal("100")
    assert h.gain_loss == Decimal("200")


# ---------------------------------------------------------------------------
# PortfolioSummary dataclass
# ---------------------------------------------------------------------------


def test_portfolio_summary_defaults() -> None:
    ps = PortfolioSummary(cash_balance=Decimal("500"), total_cost=Decimal("1000"))
    assert ps.holdings_value is None
    assert ps.roi_xirr is None
