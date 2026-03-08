# Currency Settings Guide

## Overview

Dad's Money now supports **20 different currencies** with automatic formatting. You can choose your preferred currency through the Settings dialog.

## Accessing Settings

### From the Application Menu
1. Launch Dad's Money: `./launch.sh`
2. Go to: **Edit → Settings...**
3. Choose your currency from the dropdown
4. Click **OK** to save

## Supported Currencies

The application supports 20 major world currencies:

| Code | Currency | Symbol | Decimals |
|------|----------|--------|----------|
| USD | US Dollar | $ | 2 |
| EUR | Euro | € | 2 |
| GBP | British Pound | £ | 2 |
| JPY | Japanese Yen | ¥ | 0 |
| CAD | Canadian Dollar | C$ | 2 |
| AUD | Australian Dollar | A$ | 2 |
| CHF | Swiss Franc | Fr | 2 |
| CNY | Chinese Yuan | ¥ | 2 |
| INR | Indian Rupee | ₹ | 2 |
| MXN | Mexican Peso | MX$ | 2 |
| BRL | Brazilian Real | R$ | 2 |
| ZAR | South African Rand | R | 2 |
| NZD | New Zealand Dollar | NZ$ | 2 |
| SEK | Swedish Krona | kr | 2 |
| NOK | Norwegian Krone | kr | 2 |
| DKK | Danish Krone | kr | 2 |
| SGD | Singapore Dollar | S$ | 2 |
| HKD | Hong Kong Dollar | HK$ | 2 |
| KRW | South Korean Won | ₩ | 0 |
| RUB | Russian Ruble | ₽ | 2 |

## Settings Options

### Currency
- Choose from 20 supported currencies
- Automatically adjusts:
  - Currency symbol ($, €, £, ¥, etc.)
  - Decimal places (0 for JPY/KRW, 2 for others)
  - Symbol positioning

### Thousands Separator
- **Enabled** (default): Shows `1,234.56`
- **Disabled**: Shows `1234.56`

### Date Format
- **MM/DD/YYYY** (US format) - e.g., 03/15/2026
- **DD/MM/YYYY** (UK format) - e.g., 15/03/2026
- **YYYY-MM-DD** (ISO format) - e.g., 2026-03-15
- **DD.MM.YYYY** (German format) - e.g., 15.03.2026

## Where Settings Apply

Your currency and format choices are applied throughout the application:

✓ **Account List** - Balance displays
✓ **Transaction Register** - Amount column
✓ **Account Dialogs** - Opening balance fields
✓ **Transaction Dialogs** - Amount fields
✓ **Balance Labels** - Current balance display
✓ **Date Displays** - All date columns

## Settings Storage

Settings are saved to:
```
~/Library/Application Support/DadsMoney/settings.json
```

This file is automatically created and updated when you change settings.

## Import/Export Note

When importing CSV or QIF files:
- The parser automatically **removes all common currency symbols**
- You can import files with different currency symbols
- The amounts are stored as plain numbers
- They display in your chosen currency format

## Examples

### US Dollar (USD)
- Balance: **$1,234.56**
- Spinboxes: **$ 500.00**
- Date: **03/15/2026**

### Euro (EUR)
- Balance: **€1.234,56** (with European formatting)
- Spinboxes: **€ 500,00**
- Date: **15/03/2026**

### British Pound (GBP)
- Balance: **£1,234.56**
- Date: **15/03/2026**

### Japanese Yen (JPY)
- Balance: **¥1,235** (no decimals)
- Spinboxes: **¥ 500**
- Date: **2026-03-15**

### Swiss Franc (CHF)
- Balance: **Fr 1,234.56** (space after symbol)
- Date: **15.03.2026**

## Testing Settings

Run the test script to see all currencies:
```bash
source venv/bin/activate
python test_settings.py
```

This will show:
- All available currencies
- Formatting examples
- Date format examples
- Settings save/load verification

## Changing Currency Mid-Use

You can change your currency at any time:

1. Your **data is stored as plain numbers** (no currency information)
2. Changing currency **only affects display**
3. All amounts will immediately show in the new format
4. No data is modified or lost

**Example:**
- You have an account with balance `1000`
- In USD settings: Shows as `$1,000.00`
- Switch to EUR: Shows as `€1,000.00`
- Switch to JPY: Shows as `¥1,000`
- The underlying value remains `1000`

## Multi-Currency Note

Currently, Dad's Money is a **single-currency application**:
- Choose one currency for all accounts
- All amounts display in that currency
- For multi-currency needs, consider creating separate database files

## Keyboard Shortcuts

- Open Settings: **Edit menu → Settings** (no hotkey by default)
- Save Settings: Click **OK** in the dialog
- Cancel Changes: Click **Cancel** or press **Esc**

## Default Settings

On first launch, the application uses:
- Currency: **USD** (US Dollar)
- Date format: **MM/DD/YYYY** (US format)
- Thousands separator: **Enabled**

## Troubleshooting

**Settings don't persist:**
- Check write permissions to: `~/Library/Application Support/DadsMoney/`
- Settings are saved in `settings.json`

**Currency not displaying:**
- Restart the application after changing settings
- Check that you clicked **OK** (not Cancel)

**Wrong decimal places:**
- Each currency has its own decimal precision
- This is automatic and cannot be customized
- JPY and KRW use 0 decimals (whole numbers only)
- All others use 2 decimals

---

**Settings Feature Added**: March 1, 2026
