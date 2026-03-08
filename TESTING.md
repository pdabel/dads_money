# Testing Guide for Dad's Money

This document explains how to run tests, measure coverage, and maintain the 70% coverage target.

## Quick Start

```bash
# Install development dependencies
make install-dev

# Run all tests
make test-all

# Run specific test category
make test                  # Unit tests only
make test-integration      # Integration tests only

# Check test coverage
make coverage              # Check coverage meets 70% minimum
make coverage-report       # Generate detailed HTML report
```

## Coverage Requirements

**Target: 70% code coverage** (1,852+ lines of 2,645 total)

Why 70%?
- ✅ Covers all critical paths (storage, services, import/export, settings)
- ✅ Provides safety net for making changes
- ✅ Realistic for a production application with a GUI component
- ✅ UI layer (1,279 lines) excluded—difficult and diminishing returns

### Coverage by Module (Target State)

| Module | Lines | Coverage Goal | Priority |
|--------|-------|---------------|----------|
| `storage.py` | 478 | 90%+ | Critical |
| `services.py` | 199 | 85%+ | Critical |
| `settings.py` | 150 | 85%+ | High |
| `io_csv.py` | 132 | 80%+ | High |
| `io_qif.py` | 161 | 80%+ | High |
| `models.py` | 129 | 80%+ | High |
| `io_ofx.py` | 50 | 75%+ | Medium |
| `config.py` | 38 | 75%+ | Medium |
| `ui.py` | 1,278 | N/A* | N/A |

*UI layer testing is excluded from coverage requirements due to complexity of GUI testing.

## Running Tests

### Unit Tests Only
```bash
python3 -m pytest tests/test_*.py -v
```

### Integration Tests Only
```bash
python3 -m pytest tests/integration/ -v
```

### All Tests
```bash
python3 -m pytest tests/ -v
```

### Specific Test File
```bash
python3 -m pytest tests/test_storage.py -v
python3 -m pytest tests/test_services.py::TestAccountServices -v
python3 -m pytest tests/test_models.py::TestAccount::test_account_creation -v
```

## Coverage Reports

### Terminal Report (Quick Check)
```bash
make coverage
```
Shows coverage percentage and missing lines:
```
src/dads_money/storage.py      145   120   17%  105-120, 200-210
src/dads_money/services.py     100    85   15%  50-65
...
TOTAL                        2645  1852   70%
```

### HTML Report (Detailed Analysis)
```bash
make coverage-report
open htmlcov/index.html
```

Then:
1. Click on module name to see untested lines highlighted in red
2. View branch coverage to identify complex logic without tests
3. Identify quick wins for coverage improvements

## Writing Tests to Improve Coverage

### Identify Missing Code
1. Run `make coverage-report`
2. Open `htmlcov/index.html` in browser
3. Click on modules with red lines (untested code)
4. Look for:
   - Line numbers highlighted in red = uncovered
   - Yellow = partial coverage (branches not tested)

### Example: Adding Tests for Untested Function

If `storage.py` shows line 305 uncovered:
```python
# storage.py line 305 (uncovered)
def get_account_balance_history(self, account_id: str) -> List[Tuple[date, Decimal]]:
    ...
```

Create a test:
```python
# tests/test_storage.py
def test_get_account_balance_history(self, storage: Storage, sample_account: Account) -> None:
    """Test retrieving account balance history."""
    # Create account and update balance over time
    txn1 = Transaction(account_id=sample_account.id, amount=Decimal("100.00"))
    txn2 = Transaction(account_id=sample_account.id, amount=Decimal("-50.00"))

    storage.save_transaction(txn1)
    storage.save_transaction(txn2)

    history = storage.get_account_balance_history(sample_account.id)
    assert len(history) > 0
```

### Test Coverage Checklist

For every function/method, test:

- ✅ **Happy path**: Normal operation with valid inputs
- ✅ **Edge cases**: Empty inputs, boundary values, zero/negative amounts
- ✅ **Error handling**: Invalid data, missing fields, exceptions
- ✅ **Type safety**: Decimal vs float, date formats, string encoding
- ✅ **Persistence**: Save/load round-trips for database operations
- ✅ **Integration**: Multiple components interacting

### Example Test Structure

```python
class TestNameOfFunction:
    """Tests for specific functionality."""

    def test_happy_path(self, storage: Storage) -> None:
        """Test normal operation."""
        # Setup
        account = Account(...)

        # Execute
        result = storage.get_account(account.id)

        # Verify
        assert result is not None
        assert result.name == account.name

    def test_edge_case_empty_result(self, storage: Storage) -> None:
        """Test when result is empty/null."""
        result = storage.get_account("nonexistent_id")
        assert result is None

    def test_type_preservation(self, storage: Storage) -> None:
        """Test that types are preserved through storage."""
        account = Account(opening_balance=Decimal("123.45"))
        storage.save_account(account)

        retrieved = storage.get_account(account.id)
        assert isinstance(retrieved.opening_balance, Decimal)
        assert retrieved.opening_balance == Decimal("123.45")
```

## Maintaining 70% Coverage

### Pre-Commit Checklist

Before committing code:

```bash
# 1. Format code
make format

# 2. Check style
make format-check

# 3. Run tests
make test-all

# 4. Verify coverage (MUST pass)
make coverage
```

### GitHub Actions / CI Integration

Add to `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: 3.10
      - run: pip install -e ".[dev]"
      - run: python -m pytest tests/ --cov=src/dads_money --cov-fail-under=70 -v
```

### Local Pre-Commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
echo "Running tests and coverage check..."
python3 -m pytest tests/ --cov=src/dads_money --cov-fail-under=70 -q
if [ $? -ne 0 ]; then
    echo "Coverage below 70% - commit blocked"
    exit 1
fi
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

## Coverage Evolution Target

### Phase 1: Current (40-50%) → Phase 2: (60-70%)
- Add tests for config, OFX, edge cases
- **Status**: Tests created, coverage at ~50-60%

### Phase 2: (60-70%) → Phase 3: (70%+)
- Add more edge case tests
- Test error conditions thoroughly
- Expand integration test scenarios
- **Target**: Reach 70% and enforce via CI

### Phase 3+: Maintenance (70%+)
- **Every PR must not decrease coverage below 70%**
- Pre-commit hooks enforce compliance
- CI pipeline fails if coverage drops
- Code reviews check test quality, not just coverage numbers

## Testing Best Practices

### DO ✅

- ✅ Test business logic thoroughly (services, storage)
- ✅ Test data format round-trips (CSV, QIF imports)
- ✅ Test boundary conditions (0, negative amounts, empty lists)
- ✅ Test Decimal precision (never float for currency)
- ✅ Test type preservation through storage layer
- ✅ Use fixtures for repeated setup (conftest.py)
- ✅ Group tests in classes by functionality
- ✅ Write descriptive docstrings for each test
- ✅ Test both happy path and error paths

### DON'T ❌

- ❌ Don't test framework code (PySide6, pytest internals)
- ❌ Don't aim for 100% coverage on UI
- ❌ Don't write fragile tests that break with refactoring
- ❌ Don't use real files in tests (always use temp files)
- ❌ Don't test third-party libraries (ofxparse, etc.)
- ❌ Don't write tests to document code instead of docstrings

## Troubleshooting

### Coverage higher in HTML report than terminal?
Branch coverage is included in HTML but not always shown in terminal. Run:
```bash
python3 -m pytest tests/ --cov=src/dads_money --cov-report=term-missing
```

### Specific line won't get covered?
Some lines are unreachable or require environment-specific conditions:
```python
# Mark as no cover
if os.name == 'nt':  # pragma: no cover
    # Windows-only code
    ...
```

### Need to check what breaks coverage?
```bash
python3 -m pytest tests/test_X.py --cov=src/dads_money --cov-report=term-missing -v
```

Focus on red lines (0% coverage).

### How much time for 70% coverage?
- Storage/Services tests: ~30 minutes
- Import/Export round-trips: ~20 minutes
- Edge cases and error handling: ~20 minutes
- Settings and config: ~15 minutes
- **Total**: ~1.5 hours for complete coverage

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Coverage.py documentation](https://coverage.readthedocs.io/)
- [AGENT_RULES.md](AGENT_RULES.md) - Agent development guidelines
