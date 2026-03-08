"""Pytest configuration and shared fixtures."""

import tempfile
from pathlib import Path
from typing import Generator

import pytest

from dads_money.models import Account, AccountType, Category, Transaction
from dads_money.storage import Storage


@pytest.fixture
def temp_db() -> Generator[Path, None, None]:
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_dadsmoney.db"
        yield db_path


@pytest.fixture
def storage(temp_db: Path) -> Generator[Storage, None, None]:
    """Create a storage instance with temporary database."""
    store = Storage(temp_db)
    yield store
    store.close()


@pytest.fixture
def sample_account(storage: Storage) -> Account:
    """Create a sample account for testing."""
    account = Account(
        name="Test Checking",
        account_type=AccountType.CHECKING,
        opening_balance=1000,
        current_balance=1000,
    )
    storage.save_account(account)
    return account


@pytest.fixture
def sample_category(storage: Storage) -> Category:
    """Create a sample category for testing."""
    category = Category(name="Test Expense", is_income=False)
    storage.save_category(category)
    return category


@pytest.fixture
def sample_transaction(sample_account: Account, sample_category: Category) -> Transaction:
    """Create a sample transaction for testing."""
    from decimal import Decimal

    transaction = Transaction(
        account_id=sample_account.id,
        date=None,
        payee="Test Payee",
        amount=Decimal("50.00"),
        category_id=sample_category.id,
    )
    return transaction
