# Installation Guide for Dad's Money

## Quick Start

### 1. Install Dependencies

From the project directory:

```bash
pip install -e .
```

Or install manually:

```bash
pip install PySide6 ofxparse python-dateutil
```

### 2. Run the Application

After installation, you can run the app in two ways:

**Option 1: Using the console script**
```bash
dads-money
```

**Option 2: Using the run script**
```bash
python run.py
```

**Option 3: As a module**
```bash
python -m dads_money.app
```

## Features

### Account Management
- Create multiple accounts (Checking, Savings, Credit Card, Cash, etc.)
- Track opening and current balances
- Edit and manage account details

### Transaction Register
- Add, edit, and delete transactions
- Track date, payee, amount, memo, check numbers
- Mark transactions as Cleared or Reconciled
- View transaction history by account

### Categories
- Pre-loaded with common expense and income categories
- Create custom categories
- Organize spending and income

### Import/Export
- **Import from:**
  - QIF (Quicken Interchange Format)
  - OFX (Open Financial Exchange - bank downloads)
  - CSV (Comma-Separated Values)

- **Export to:**
  - QIF format
  - CSV format

### Data Storage
- SQLite database for reliable, portable storage
- Database located in platform-specific user data directory:
  - macOS: `~/Library/Application Support/DadsMoney/dadsmoney.db`
  - Linux: `~/.local/share/DadsMoney/dadsmoney.db`
  - Windows: `%APPDATA%\DadsMoney\dadsmoney.db`

## User Interface

The application mimics the classic Microsoft Money 3.0 interface:

- **Left Panel**: Account list with balances
- **Right Panel**: Transaction register for selected account
- **Toolbar**: Quick access to common operations
- **Menus**: File, Edit, and Help menus

## Tips

1. **Start by creating an account**: Click "New Account" or use File → New Account
2. **Add transactions**: Select an account and click "New Transaction"
3. **Import existing data**: Use File → Import to bring in QIF, OFX, or CSV files
4. **Organize with categories**: Use Edit → Categories to customize your category list
5. **Export for backup**: Use File → Export to create QIF or CSV backups

## Keyboard Shortcuts

- Common dialogs support Tab navigation
- Enter/Return confirms dialogs
- Escape cancels dialogs

## Troubleshooting

### Application won't start
- Ensure Python 3.10+ is installed
- Verify all dependencies are installed: `pip install -e .`

### Import fails
- Check file format (QIF, OFX, or CSV)
- Ensure file is not corrupted
- For OFX: verify ofxparse library is installed

### Database issues
- Check write permissions in user data directory
- Database file: Use SQLite browser to inspect if needed

## Development

### Running Tests
```bash
pip install -e ".[dev]"
pytest
```

### Code Formatting
```bash
black src/
```

## License

MIT License
