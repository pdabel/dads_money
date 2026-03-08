# Agent Rules for DadsMoney Development

Guidelines for agents implementing features or making changes to the DadsMoney codebase. These rules ensure consistency, maintainability, and preserve critical project functionality.

---

## 1. Code Style & Quality

**Type Hints (MUST)**: All function signatures and class methods MUST include complete type hints. Follow the style in [src/dads_money/models.py](src/dads_money/models.py) and [src/dads_money/services.py](src/dads_money/services.py).
```python
def create_account(self, name: str, account_type: str, currency: str) -> Account:
```

**Naming Conventions (MUST)**:
- Classes: PascalCase (`QIFParser`, `MainWindow`, `MoneyService`)
- Functions/methods: snake_case (`parse_file()`, `create_account()`)
- Constants: UPPER_SNAKE_CASE (`DEFAULT_SETTINGS`, `REGISTER_COLUMNS`)
- Private methods: prefix with underscore (`_parse_date()`, `_validate_splits()`)

**Black Formatter (MUST)**: Run `black src/ --line-length 100 --target-version py310` before committing code changes. Project uses line-length of 100 and targets Python 3.10+.

**No Suppression to “Go Green” (MUST)**: Agents MUST fix root causes instead of hiding failures.
- **Forbidden**: `|| true`, blanket lint/type suppressions, and disabling checks in CI just to pass.
- **Forbidden**: broad mypy flags like global `--ignore-missing-imports` when they hide real project issues.
- **Allowed only when unavoidable**: narrowly scoped suppression for third-party limitations (e.g., missing stubs), with explicit module-level targeting and a short rationale in config.
- **When blocked**: report the blocker clearly and keep checks honest (do not mask failures).

**Docstrings (MUST)**: All public functions and classes MUST have docstrings. Include Args and Returns for clarity. Example from [src/dads_money/storage.py](src/dads_money/storage.py):
```python
def get_account(self, account_id: int) -> Account | None:
    """Retrieve an account by ID. Returns None if not found."""
```

---

## 2. Data Constraints

**Currency: Decimal Only (MUST)**: All monetary amounts MUST use `Decimal` type, never `float`. Follow patterns in [src/dads_money/models.py](src/dads_money/models.py) where `amount: Decimal` is validated in `__post_init__`.

**Validate in __post_init__ (MUST)**: For dataclass models (Account, Transaction, Category, Split), validate types and constraints in `__post_init__` method. Ensure Decimal conversion and range checks occur here.

**No Currency Arithmetic Without Context (SHOULD)**: When performing currency calculations, use the account's or transaction's currency setting from [src/dads_money/settings.py](src/dads_money/settings.py) to determine formatting rules. Never assume USD.

---

## 3. Testing & Validation

**Unit Tests for All Changes (MUST)**: Every code change MUST include corresponding unit tests. Create or update tests in the `tests/` directory following pytest patterns. Run `make test` to verify. Tests should cover:
- Normal operation (happy path)
- Edge cases (empty inputs, boundary values)
- Error handling (invalid data, exceptions)
- Example: If adding a method to `MoneyService`, add tests in `tests/test_services.py`

**Checks Must Fail Loudly (MUST)**: CI and local validation commands must surface real failures.
- Do not swallow non-zero exits from `pytest`, `mypy`, or formatting checks.
- If a rule must be scoped down temporarily, prefer precise allowlists over global disables, and document the reason.

**Integration Tests for Database/Import-Export (MUST)**: When modifying [src/dads_money/storage.py](src/dads_money/storage.py) or import/export modules ([src/dads_money/io_qif.py](src/dads_money/io_qif.py), [src/dads_money/io_csv.py](src/dads_money/io_csv.py), [src/dads_money/io_ofx.py](src/dads_money/io_ofx.py)), MUST add or update integration tests in `tests/integration/`. These tests should verify:
- Full round-trip workflows (create → save → load → verify)
- Cross-module interactions (service calling storage calling database)
- Format compatibility (parse file → verify format → export → re-parse)
- Run with `make test-integration`

**Verify QIF Module Continuity (MUST)**: Any changes to imports or core modules MUST verify that `from dads_money.io_qif import QIFParser, QIFWriter` continues to work. The QIF module is a custom implementation at [src/dads_money/io_qif.py](src/dads_money/io_qif.py) (not an external library) and supports bidirectional file I/O. Include QIF import test in unit tests.

**Test Manual Validation Pattern (SHOULD)**: Follow the manual testing approach in [test_settings.py](test_settings.py) for quick feature validation. Create a standalone test script that demonstrates functionality with print output for exploratory testing.

**Cross-Platform Path Handling (SHOULD)**: When working with file paths, use patterns from [src/dads_money/config.py](src/dads_money/config.py) to ensure compatibility across macOS, Linux, and Windows. Database paths, settings files, and exports should adapt per platform.

**Optional Dependency Checks (SHOULD)**: For optional modules like `ofxparse`, follow the pattern in [src/dads_money/io_ofx.py](src/dads_money/io_ofx.py) with try-except import blocks and an `is_available()` check at runtime.

---

## 4. Documentation Updates

**Update README.md Feature Checklist (MUST)**: If adding or modifying features that affect the feature list, update the corresponding checklist in [README.md](README.md). Use ✓ or ✅ for complete features.

**Update IMPLEMENTATION.md (MUST)**: If adding new files, modifying module structure, or significantly changing line counts, update the file listing and line count summary in [IMPLEMENTATION.md](IMPLEMENTATION.md). This document should reflect the current state of the codebase.

**Maintain Documentation Style (SHOULD)**: Follow existing markdown conventions in [README.md](README.md), [QUICKSTART.md](QUICKSTART.md), and [CURRENCY_GUIDE.md](CURRENCY_GUIDE.md): use section headers, code blocks with language specified, bullet points, tables, and command examples with bash syntax highlighting.

**Mark Status (CONSIDER)**: Use status labels like "COMPLETE AND READY TO USE" or version notes in documentation to help users understand feature completeness.

---

## 5. Feature Compatibility

**Preserve Money 3.0 Parity (MUST)**: The application is designed for Microsoft Money 3.0 compatibility. Maintain the existing 7 account types (Current Account, Savings, Credit Card, Cash, Investment, Asset, Liability), with Savings accounts supporting 4 subtypes (Standard Savings, High Interest Savings, Cash ISA, Stocks & Shares ISA). Maintain transaction fields (Date, Reference#, Payee, Memo, Status, Amount), and category structure (17 pre-loaded, income/expense/tax flags).

**Support 20 Currencies (MUST)**: The project supports 20 currencies with proper formatting. Changes to currency handling or addition of new currencies MUST maintain this list and update [CURRENCY_GUIDE.md](CURRENCY_GUIDE.md) accordingly.

**Maintain QIF Bidirectional Support (MUST)**: QIF import/export is a core feature. Any modifications to transaction models or data structures MUST preserve the ability to round-trip data through QIF (parse from file and write back correctly). Reference [src/dads_money/io_qif.py](src/dads_money/io_qif.py) for current format support.

**Production-Ready Quality (SHOULD)**: The codebase is marked as "COMPLETE AND READY TO USE." Maintain this status by ensuring changes do not introduce breaking bugs, maintain backward compatibility with existing databases, and preserve all currently documented features.

---

## 6. Test-Driven Development (TDD)

**Core Logic — MUST Use TDD**: For storage, services, import/export, settings, and models layers, write failing tests first, then implement code to pass them. This ensures deterministic behavior and fast feedback loops.
- **Storage Layer** ([src/dads_money/storage.py](src/dads_money/storage.py)): Write CRUD test → implement database operation → verify with `make test`
- **Services Layer** ([src/dads_money/services.py](src/dads_money/services.py)): Test business logic (account/transaction operations) before implementation
- **Import/Export** ([io_csv.py](src/dads_money/io_csv.py), [io_qif.py](src/dads_money/io_qif.py), [io_ofx.py](src/dads_money/io_ofx.py)): Test edge cases (malformed data, unicode, large amounts) upfront
- **Settings/Config** ([settings.py](src/dads_money/settings.py), [config.py](src/dads_money/config.py)): Test all 20 currencies and cross-platform paths before implementation
- **Models** ([models.py](src/dads_money/models.py)): Test Decimal precision and validation constraints first

**UI Layer — DO NOT Use TDD**: PySide6 widget testing is fragile, slow, and has diminishing returns. Instead:
- Implement UI code → manually test in running application → write integration tests for data flow
- Example: New dialog → code it → test dialogs/buttons in GUI → write integration test for storage/services interaction
- Focus integration tests on workflows (account → transaction → export), not UI widgets
- Reference: [src/dads_money/ui.py](src/dads_money/ui.py)

**Integration Tests — Write After Feature Works**: Test complete workflows that exercise both UI and core logic. Write these after the feature is working.
- **Workflows**: Account creation → transaction entry → balance updates → export
- **Round-trips**: Import QIF → parse → verify data → export → re-parse
- **Multi-component interactions**: Service calling storage calling database
- Run with `make test-integration`

**TDD Workflow Example**:
```
1. RED:   Write test that fails
   pytest tests/test_storage.py::TestAccountStorage::test_save_and_retrieve_account

2. GREEN: Implement code to pass test
   Edit src/dads_money/storage.py → save_account()

3. REFACTOR: Clean up code while keeping test passing
   make format && make test
```

**When to Apply TDD:**
- ✅ Adding new business logic (accounts, transactions, categories)
- ✅ Fixing bugs (write failing test first, then fix)
- ✅ Adding edge case handling (unicode, large numbers, empty inputs)
- ✅ Data format changes (CSV/QIF parsing rules)
- ❌ UI implementation (manual test first)
- ❌ Refactoring existing core code (write tests after, then refactor safely)

---

## Quick Reference

| Aspect | Rule | Reference |
|--------|------|-----------|
| Import Check | QIF must continue to work | [io_qif.py](src/dads_money/io_qif.py) |
| Unit Tests | Required for all changes | Run: `make test` |
| Integration Tests | Required for DB/import-export changes | Run: `make test-integration` |
| TDD for Logic | Write tests first (storage, services, import/export) | [TESTING.md](TESTING.md) |
| NO TDD for UI | Manual test, then integration tests | [ui.py](src/dads_money/ui.py) |
| Currency Type | Always use Decimal, never float | [models.py](src/dads_money/models.py) |
| Type Hints | Required on all functions | [services.py](src/dads_money/services.py) |
| Documentation | Update README + IMPLEMENTATION.md | [README.md](README.md), [IMPLEMENTATION.md](IMPLEMENTATION.md) |
| Format Code | Run Black before commit | Line length: 100, Python 3.10+ |
| Code Quality | Run all checks | `make check` (lint + format-check) |
| Coverage | Maintain 70% minimum | `make coverage` |
