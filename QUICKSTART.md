# Dad's Money - Quick Start Guide

## ✅ Implementation Complete

A Microsoft Money 3.0 compatible personal finance application has been successfully implemented in Python.

## 🚀 How to Launch

### Method 1: Using the launcher script (Recommended)
```bash
./launch.sh
```

### Method 2: Manual activation
```bash
source venv/bin/activate
python run.py
```

### Method 3: Using installed command
```bash
source venv/bin/activate
dads-money
```

## � Build Standalone App (Optional)

### Create macOS Application Bundle

To distribute to others without Python:

```bash
./build_installer.sh
```

**Creates:**
- `dist/DadsMoney.app` - Standalone macOS app (~100 MB)
- `dist/INSTALLATION_INSTRUCTIONS.txt` - User guide
- DMG installer (if create-dmg installed)

**Share with:**
- Friends and family
- Multiple Macs
- Users without Python

See [BUILDING.md](BUILDING.md) for details.

## �📋 What's Included

### ✓ Core Features (Microsoft Money 3.0 Compatible)

1. **Account Management**
   - Create accounts: Checking, Savings, Credit Card, Cash, Investment, Assets, Liabilities
   - Track balances automatically
   - Edit and manage account details
   - View all accounts in sidebar

2. **Transaction Register**
   - Add/edit/delete transactions
   - Fields: Date, Check #, Payee, Amount, Memo, Status
   - Transaction statuses: Uncleared, Cleared, Reconciled
   - Automatic balance calculation
   - Sort by date

3. **Categories**
   - 17 pre-loaded categories (matching Money 3.0)
   - Create custom categories
   - Income vs. Expense tracking
   - Tax-related flagging

4. **Import/Export**
   - **QIF Import/Export** - Microsoft Money's primary format
   - **CSV Import/Export** - Spreadsheet compatibility
   - **OFX Import** - Direct bank downloads

5. **Data Storage**
   - SQLite database
   - Location: `~/Library/Application Support/DadsMoney/dadsmoney.db`
   - Portable and reliable

### ✓ User Interface (Money 3.0 Style)

- **Two-pane layout**: Accounts (left) | Register (right)
- **Menu bar**: File, Edit, Help
- **Toolbar**: Quick access buttons
- **Dialogs**: Account, Transaction, Category management
- **Platform-native** look and feel using Qt6

## 🧪 Try the Demo

Run the included demonstration to see all features in action:

```bash
source venv/bin/activate
python demo.py
```

The demo will:
- Create sample accounts (Checking, Savings, Credit Card)
- Add sample transactions (paycheck, groceries, gas, rent)
- Show balance calculations
- Export to QIF and CSV formats
- Display transaction register

## 📁 Project Structure

```
/Users/paul/python/dads_money/
├── launch.sh              # Quick launcher script
├── run.py                 # Manual launcher
├── demo.py                # Feature demonstration
├── README.md              # Full documentation
├── INSTALL.md             # Installation guide
├── pyproject.toml         # Package configuration
├── venv/                  # Virtual environment (installed)
└── src/dads_money/        # Application code
    ├── app.py             # Entry point
    ├── ui.py              # Money 3.0 style GUI
    ├── models.py          # Data models
    ├── storage.py         # SQLite database
    ├── services.py        # Business logic
    ├── settings.py        # User preferences (currency, date format)
    ├── io_qif.py          # QIF import/export
    ├── io_csv.py          # CSV import/export
    ├── io_ofx.py          # OFX import
    └── config.py          # Configuration
    ├── io_csv.py          # CSV import/export
    ├── io_ofx.py          # OFX import
    └── config.py          # Configuration
```

## 💡 Usage Workflow

### 1. Launch the Application
```bash
./launch.sh
```

### 2. Create Your First Account
- Click "New Account" button
- Enter name (e.g., "My Checking")
- Select type (Checking)
- Enter opening balance
- Click OK

### 3. Add a Transaction
- Select the account in the left panel
- Click "New Transaction"
- Enter details:
  - Date (use calendar picker)
  - Payee (e.g., "Grocery Store")
  - Amount (negative for expenses)
  - Memo (optional)
  - Check # (optional)
  - Status (Uncleared/Cleared/Reconciled)
- Click OK

### 4. Import Existing Data
- File → Import
- Select file type (QIF, OFX, or CSV)
- Choose file
- Transactions imported to selected account

### 5. Export for Backup
- Select account
- File → Export
- Choose format (QIF or CSV)
- Save file

## 🎨 UX Notes (Microsoft Money 3.0 Match)

The interface closely mimics Microsoft Money 3.0:

- **Account List**: Left sidebar with names and balances
- **Register View**: Spreadsheet-style transaction list
- **Dialog Style**: Simple forms matching Money 3.0 aesthetics
- **Button Layout**: Toolbar + contextual buttons
- **Status Indicators**: C (Cleared), R (Reconciled)
- **Menu Structure**: File/Edit/Help hierarchy

Ready to re-skin later with exact Money 3.0 colors, fonts, and icons.

## ✅ Platform Independence

Built for cross-platform compatibility:
- **Language**: Python 3.10+
- **GUI Framework**: PySide6 (Qt6)
- **Database**: SQLite
- **Works on**: macOS, Linux, Windows

## 📊 File Format Compatibility

### QIF (Quicken Interchange Format)
- Full read/write support
- Compatible with Microsoft Money 3.0 exports
- Fields: Date, Amount, Payee, Memo, Check #, Status
- Account types: Bank, Cash, CCard

### CSV (Comma-Separated Values)
- Flexible import with column auto-detection
- Standard export format
- Compatible with Excel, Google Sheets

### OFX (Open Financial Exchange)
- Import-only for bank downloads
- Modern replacement for QIF
- Requires ofxparse library (installed)

## 🔧 Next Steps (Optional Enhancements)

The core application is complete. Optional future enhancements:

1. **Visual Styling**: Add Money 3.0 exact colors, fonts, icons
2. **Split Transactions**: UI for split entry
3. **Reports**: Basic income/expense reports
4. **Budgets**: Budget tracking
5. **Reconciliation**: Account reconciliation wizard
6. **Search**: Transaction search and filtering
7. **Transfers**: Better transfer account handling

## 📞 Support

- Full documentation: [README.md](README.md)
- Installation help: [INSTALL.md](INSTALL.md)
- Demo script: `python demo.py`

---

**Status**: ✅ **Implementation Complete and Ready to Use**

Launch the application with `./launch.sh` and start managing your finances!
