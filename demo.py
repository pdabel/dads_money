"""
Demo script showing Dad's Money functionality.

This script demonstrates:
- Creating accounts
- Adding transactions
- Using categories
- Importing/exporting data
"""

from datetime import date
from decimal import Decimal
from pathlib import Path
import tempfile

from dads_money.models import AccountType, TransactionStatus
from dads_money.services import MoneyService


def demo():
    """Run a demonstration of Dad's Money features."""

    # Create a temporary database for the demo
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)

    print("=" * 60)
    print("Dad's Money - Demonstration")
    print("=" * 60)
    print()

    # Initialize service
    print("Initializing Dad's Money...")
    service = MoneyService(db_path)
    print(f"✓ Database created at: {db_path}")
    print()

    # Create accounts
    print("Creating accounts...")
    checking = service.create_account(
        name="My Checking", account_type=AccountType.CHECKING, opening_balance=1000.00
    )
    print(f"✓ Created: {checking.name} - ${checking.current_balance}")

    savings = service.create_account(
        name="Savings Account", account_type=AccountType.SAVINGS, opening_balance=5000.00
    )
    print(f"✓ Created: {savings.name} - ${savings.current_balance}")

    credit_card = service.create_account(
        name="Credit Card", account_type=AccountType.CREDIT_CARD, opening_balance=0.00
    )
    print(f"✓ Created: {credit_card.name} - ${credit_card.current_balance}")
    print()

    # List categories
    print("Available categories:")
    categories = service.get_all_categories()
    income_cats = [c for c in categories if c.is_income]
    expense_cats = [c for c in categories if not c.is_income]
    print(f"  Income categories: {len(income_cats)}")
    print(f"  Expense categories: {len(expense_cats)}")
    for cat in expense_cats[:5]:
        print(f"    - {cat.name}")
    print(f"    ... and {len(expense_cats) - 5} more")
    print()

    # Create transactions
    print("Adding transactions to checking account...")

    # Paycheck
    trans1 = service.create_transaction(
        account_id=checking.id,
        date=date(2026, 3, 1),
        amount=Decimal("2500.00"),
        payee="Employer Inc.",
        memo="Bi-weekly paycheck",
    )
    trans1.status = TransactionStatus.CLEARED
    service.update_transaction(trans1)
    print(f"✓ Added: {trans1.payee} - ${trans1.amount}")

    # Groceries
    trans2 = service.create_transaction(
        account_id=checking.id,
        date=date(2026, 3, 2),
        amount=Decimal("-125.50"),
        payee="Grocery Store",
        memo="Weekly groceries",
    )
    print(f"✓ Added: {trans2.payee} - ${trans2.amount}")

    # Gas
    trans3 = service.create_transaction(
        account_id=checking.id,
        date=date(2026, 3, 3),
        amount=Decimal("-45.00"),
        payee="Gas Station",
        memo="Fill up",
        check_number="",
    )
    print(f"✓ Added: {trans3.payee} - ${trans3.amount}")

    # Check
    trans4 = service.create_transaction(
        account_id=checking.id,
        date=date(2026, 3, 4),
        amount=Decimal("-800.00"),
        payee="Landlord",
        memo="March rent",
        check_number="1001",
    )
    trans4.status = TransactionStatus.RECONCILED
    service.update_transaction(trans4)
    print(f"✓ Added: {trans4.payee} - ${trans4.amount} (Check #{trans4.check_number})")
    print()

    # Show updated balances
    print("Current account balances:")
    all_accounts = service.get_all_accounts()
    total = Decimal("0.00")
    for acc in all_accounts:
        acc_updated = service.get_account(acc.id)
        print(f"  {acc_updated.name:20} ${acc_updated.current_balance:>10,.2f}")
        total += acc_updated.current_balance
    print(f"  {'─' * 20} {'─' * 12}")
    print(f"  {'Total Net Worth':20} ${total:>10,.2f}")
    print()

    # Test export
    print("Testing QIF export...")
    qif_file = db_path.parent / "demo_export.qif"
    service.export_qif(str(qif_file), checking.id)
    print(f"✓ Exported to: {qif_file}")
    print()

    # Show QIF content
    print("QIF file preview (first 15 lines):")
    with open(qif_file, "r") as f:
        lines = f.readlines()[:15]
        for line in lines:
            print(f"  {line.rstrip()}")
    if len(lines) >= 15:
        print("  ...")
    print()

    # Test CSV export
    print("Testing CSV export...")
    csv_file = db_path.parent / "demo_export.csv"
    service.export_csv(str(csv_file), checking.id)
    print(f"✓ Exported to: {csv_file}")
    print()

    # Show transaction details
    print("Transaction register for", checking.name + ":")
    print(f"  {'Date':<12} {'Check':<8} {'Payee':<20} {'Status':<6} {'Amount':>12}")
    print(f"  {'-'*12} {'-'*8} {'-'*20} {'-'*6} {'-'*12}")

    transactions = service.get_transactions_for_account(checking.id)
    for trans in reversed(transactions):  # Show oldest first
        status_char = ""
        if trans.status == TransactionStatus.RECONCILED:
            status_char = "R"
        elif trans.status == TransactionStatus.CLEARED:
            status_char = "C"

        print(
            f"  {trans.date.strftime('%m/%d/%Y'):<12} "
            f"{trans.check_number:<8} "
            f"{trans.payee[:20]:<20} "
            f"{status_char:<6} "
            f"${trans.amount:>11,.2f}"
        )

    print()
    print("=" * 60)
    print("Demo complete!")
    print()
    print(f"Demo files:")
    print(f"  Database: {db_path}")
    print(f"  QIF export: {qif_file}")
    print(f"  CSV export: {csv_file}")
    print()
    print("To launch the GUI application, run:")
    print("  ./launch.sh")
    print("  or")
    print("  source venv/bin/activate && python run.py")
    print("=" * 60)

    # Cleanup
    service.close()


if __name__ == "__main__":
    demo()
