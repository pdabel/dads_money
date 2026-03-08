# Dad's Money

A Microsoft Money 3.0 compatible personal finance application for macOS (and other platforms).

## Quick Start

### Running the Application

**Option 1: Using the launcher script (easiest on macOS)**
```bash
./launch.sh
```

**Option 2: Activate venv manually**
```bash
source venv/bin/activate
python run.py
```

**Option 3: Using the installed console command**
```bash
source venv/bin/activate
dads-money
```

## Features

### Microsoft Money 3.0 Compatible Interface
- Classic two-pane layout: Account list on left, transaction register on right
- Familiar menu structure (File, Edit, Help)
- Traditional toolbar with quick actions
- Transaction register with columns for Date, Reference #, Payee, Memo, Status, and Amount

### Account Management
- Create multiple account types:
  - Current accounts (checking)
  - Savings accounts with subtypes:
    - Standard Savings
    - High Interest Savings
    - Cash ISA
    - Stocks and Shares ISA
  - Credit cards
  - Cash accounts
  - Investment accounts
  - Assets and Liabilities
- Track opening and current balances
- View account details and balances in sidebar
- Edit account properties

### Transaction Register
- Double-entry accounting transactions
- Fields matching Money 3.0:
  - Date (with calendar picker)
  - Reference number (for cheques, direct debits, or transaction IDs)
  - Payee
  - Amount
  - Status (Uncleared, Cleared, Reconciled)
  - Memo
- Add, edit, and delete transactions
- Automatic balance calculation
- Transaction history sorted by date

### Categories
- Pre-loaded with common expense and income categories:
  - Income: Salary, etc.
  - Expenses: Auto, Bills, Dining, Entertainment, Groceries, Healthcare, Home, Insurance, Taxes, Utilities, etc.
- Create custom categories
- Manage and delete categories
- Support for income vs. expense categorization
- Tax-related category flagging

### Settings & Preferences
- **Multi-Currency Support**: Choose from 20 world currencies (USD, EUR, GBP, JPY, CAD, AUD, and more)
- **Currency Formatting**: Automatic symbol, decimal places, and thousands separator
- **Date Formats**: US (MM/DD/YYYY), UK (DD/MM/YYYY), ISO (YYYY-MM-DD), German (DD.MM.YYYY)
- **Persistent Settings**: Preferences saved to `settings.json`
- See [CURRENCY_GUIDE.md](CURRENCY_GUIDE.md) for complete currency documentation

### Import/Export (Money 3.0 Compatible)
- **Import from:**
  - **QIF (Quicken Interchange Format)**: Primary Microsoft Money export format
  - **OFX (Open Financial Exchange)**: Direct bank downloads
  - **CSV (Comma-Separated Values)**: Spreadsheet data

- **Export to:**
  - **QIF format**: Compatible with Money, Quicken, and other financial software
  - **CSV format**: For spreadsheets and analysis

### Data Storage
- SQLite database for reliable, portable storage
- Cross-platform file location:
  - **macOS**: `~/Library/Application Support/DadsMoney/dadsmoney.db`
  - **Linux**: `~/.local/share/DadsMoney/dadsmoney.db`
  - **Windows**: `%APPDATA%\DadsMoney\dadsmoney.db`
- Automatic schema creation
- Transaction history preserved
- Balance tracking and reconciliation

## User Interface

The application closely mimics the Microsoft Money 3.0 interface:

### Layout
- **Left Panel**: Account list showing all accounts with current balances
- **Right Panel**: Transaction register for the selected account
- **Menu Bar**: File, Edit, and Help menus with standard operations
- **Toolbar**: Quick access buttons for common tasks
- **Status Bar**: Shows current operation status and messages

### Dialogs
- Account creation/editing dialog
- Transaction entry dialog with all Money 3.0 fields
- Category management dialog
- File import/export dialogs

## Installation

See [INSTALL.md](INSTALL.md) for detailed installation instructions.

### Prerequisites
- Python 3.10 or higher
- Virtual environment (included)

### Dependencies (auto-installed)
- PySide6 (Qt6 for Python - cross-platform GUI)
- ofxparse (OFX file parsing)
- python-dateutil (date handling)

## Architecture

```
src/dads_money/
├── __init__.py          # Package initialization
├── app.py              # Application entry point
├── config.py           # Configuration and paths
├── models.py           # Data models (Account, Transaction, Category, Split)
├── storage.py          # SQLite database layer
├── services.py         # Business logic layer
├── ui.py               # PySide6 GUI (Money 3.0 style)
├── io_qif.py           # QIF import/export
├── io_csv.py           # CSV import/export
└── io_ofx.py           # OFX import
```

## Usage Tips

1. **Create your first account**: Click "New Account" button or File → New Account
2. **Select savings type**: When creating a savings account, choose the appropriate subtype (Standard, High Interest, Cash ISA, or Stocks & Shares ISA)
3. **Add transactions**: Select an account, then click "New Transaction"
4. **Choose your currency**: Edit → Settings to select from 20 currencies and set date format (defaults to GBP and UK date format)
5. **Import existing data**: File → Import, then select QIF, OFX, or CSV file
6. **Mark transactions cleared**: Edit a transaction and change Status to "Cleared" or "Reconciled"
7. **Organize spending**: Edit → Categories to customize your category list
8. **Export for backup**: File → Export to create QIF or CSV backup files

## Building & Distribution

### Create Standalone macOS App

Build a distributable .app bundle that runs without Python installed:

```bash
./build_installer.sh
```

**Output:**
- `dist/DadsMoney.app` - Standalone macOS application
- `dist/DadsMoney-Installer.dmg` - DMG installer (if create-dmg installed)
- `dist/INSTALLATION_INSTRUCTIONS.txt` - User installation guide

**Distribution:**
- Share the .app or DMG with friends/family
- No Python or dependencies needed on their Mac
- Simple "right-click → Open" on first launch
- See [BUILDING.md](BUILDING.md) for complete guide

## Development

```bash
# Install with dev dependencies
source venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
```

## Compatibility Notes

### File Format Support
- **QIF**: Full bidirectional support for Microsoft Money 3.0 QIF exports
- **OFX**: Import-only support for modern bank downloads
- **CSV**: Flexible import with auto-detection of common column formats

### Platform Independence
- Built with Python for maximum portability
- PySide6 provides native look and feel on macOS, Linux, and Windows
- SQLite database works identically across all platforms
- File paths automatically adapt to OS conventions

## License

MIT License
