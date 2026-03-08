"""User settings and preferences."""

import json
from pathlib import Path
from typing import Optional

from .config import Config

# Common currency symbols
CURRENCIES = {
    "USD": {"symbol": "$", "name": "US Dollar", "decimal_places": 2},
    "EUR": {"symbol": "€", "name": "Euro", "decimal_places": 2},
    "GBP": {"symbol": "£", "name": "British Pound", "decimal_places": 2},
    "JPY": {"symbol": "¥", "name": "Japanese Yen", "decimal_places": 0},
    "CAD": {"symbol": "C$", "name": "Canadian Dollar", "decimal_places": 2},
    "AUD": {"symbol": "A$", "name": "Australian Dollar", "decimal_places": 2},
    "CHF": {"symbol": "Fr", "name": "Swiss Franc", "decimal_places": 2},
    "CNY": {"symbol": "¥", "name": "Chinese Yuan", "decimal_places": 2},
    "INR": {"symbol": "₹", "name": "Indian Rupee", "decimal_places": 2},
    "MXN": {"symbol": "MX$", "name": "Mexican Peso", "decimal_places": 2},
    "BRL": {"symbol": "R$", "name": "Brazilian Real", "decimal_places": 2},
    "ZAR": {"symbol": "R", "name": "South African Rand", "decimal_places": 2},
    "NZD": {"symbol": "NZ$", "name": "New Zealand Dollar", "decimal_places": 2},
    "SEK": {"symbol": "kr", "name": "Swedish Krona", "decimal_places": 2},
    "NOK": {"symbol": "kr", "name": "Norwegian Krone", "decimal_places": 2},
    "DKK": {"symbol": "kr", "name": "Danish Krone", "decimal_places": 2},
    "SGD": {"symbol": "S$", "name": "Singapore Dollar", "decimal_places": 2},
    "HKD": {"symbol": "HK$", "name": "Hong Kong Dollar", "decimal_places": 2},
    "KRW": {"symbol": "₩", "name": "South Korean Won", "decimal_places": 0},
    "RUB": {"symbol": "₽", "name": "Russian Ruble", "decimal_places": 2},
}


class Settings:
    """User settings and preferences."""

    DEFAULT_SETTINGS = {
        "currency_code": "GBP",
        "date_format": "%d/%m/%Y",  # UK format by default
        "thousands_separator": True,
        "show_cleared_status": True,
        "window_width": 1200,
        "window_height": 700,
    }

    def __init__(self):
        """Initialize settings."""
        self.settings_file = Config.get_user_data_dir() / "settings.json"
        self._settings = self.DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        """Load settings from file."""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r") as f:
                    saved = json.load(f)
                    self._settings.update(saved)
            except Exception as e:
                print(f"Error loading settings: {e}")

    def save(self):
        """Save settings to file."""
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, "w") as f:
                json.dump(self._settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def get(self, key: str, default=None):
        """Get a setting value."""
        return self._settings.get(key, default)

    def set(self, key: str, value):
        """Set a setting value."""
        self._settings[key] = value

    # Currency helpers
    @property
    def currency_code(self) -> str:
        """Get the currency code."""
        return self._settings.get("currency_code", "USD")

    @currency_code.setter
    def currency_code(self, code: str):
        """Set the currency code."""
        if code in CURRENCIES:
            self._settings["currency_code"] = code

    @property
    def currency_symbol(self) -> str:
        """Get the currency symbol."""
        code = self.currency_code
        return CURRENCIES.get(code, CURRENCIES["USD"])["symbol"]

    @property
    def currency_name(self) -> str:
        """Get the currency name."""
        code = self.currency_code
        return CURRENCIES.get(code, CURRENCIES["USD"])["name"]

    @property
    def decimal_places(self) -> int:
        """Get the number of decimal places for the currency."""
        code = self.currency_code
        return CURRENCIES.get(code, CURRENCIES["USD"])["decimal_places"]

    def format_currency(self, amount, include_symbol: bool = True) -> str:
        """Format an amount as currency."""
        symbol = self.currency_symbol if include_symbol else ""
        decimal_places = self.decimal_places
        use_thousands = self._settings.get("thousands_separator", True)

        if use_thousands:
            formatted = f"{float(amount):,.{decimal_places}f}"
        else:
            formatted = f"{float(amount):.{decimal_places}f}"

        if include_symbol:
            # Add space between symbol and amount for some currencies
            if symbol in ["Fr", "kr", "R"]:
                return f"{symbol} {formatted}"
            else:
                return f"{symbol}{formatted}"
        return formatted

    @property
    def date_format(self) -> str:
        """Get the date format string."""
        return self._settings.get("date_format", "%m/%d/%Y")

    @date_format.setter
    def date_format(self, fmt: str):
        """Set the date format string."""
        self._settings["date_format"] = fmt


# Global settings instance
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
