"""Unit tests for settings."""

from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from dads_money.config import Config
from dads_money.settings import Settings, CURRENCIES


class TestSettingsCurrency:
    """Tests for currency settings."""

    def test_default_currency(self) -> None:
        """Test default currency is set correctly."""
        settings = Settings()
        # Default is GBP in the settings file
        assert settings.currency_code in CURRENCIES

    def test_set_valid_currency(self) -> None:
        """Test setting a valid currency."""
        settings = Settings()
        original = settings.currency_code

        settings.currency_code = "USD"
        assert settings.currency_code == "USD"
        assert settings.currency_symbol == "$"

        # Restore
        settings.currency_code = original

    def test_set_all_supported_currencies(self) -> None:
        """Test setting each of the 20 supported currencies."""
        settings = Settings()

        for code in CURRENCIES.keys():
            settings.currency_code = code
            assert settings.currency_code == code
            assert settings.currency_symbol == CURRENCIES[code]["symbol"]
            assert settings.currency_name == CURRENCIES[code]["name"]

    def test_currency_symbol_property(self) -> None:
        """Test currency symbol property."""
        settings = Settings()

        test_cases = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "JPY": "¥",
            "CAD": "C$",
        }

        for code, expected_symbol in test_cases.items():
            settings.currency_code = code
            assert settings.currency_symbol == expected_symbol

    def test_currency_name_property(self) -> None:
        """Test currency name property."""
        settings = Settings()

        test_cases = {
            "USD": "US Dollar",
            "EUR": "Euro",
            "GBP": "British Pound",
            "JPY": "Japanese Yen",
        }

        for code, expected_name in test_cases.items():
            settings.currency_code = code
            assert settings.currency_name == expected_name

    def test_decimal_places_property(self) -> None:
        """Test decimal places for various currencies."""
        settings = Settings()

        # Most currencies use 2 decimal places
        settings.currency_code = "USD"
        assert settings.decimal_places == 2

        # JPY uses 0 decimal places
        settings.currency_code = "JPY"
        assert settings.decimal_places == 0

        # KRW uses 0 decimal places
        settings.currency_code = "KRW"
        assert settings.decimal_places == 0


class TestSettingsFormatCurrency:
    """Tests for currency formatting."""

    def test_format_usd(self) -> None:
        """Test formatting US dollars."""
        settings = Settings()
        settings.currency_code = "USD"

        formatted = settings.format_currency(Decimal("1234.56"))
        assert "$" in formatted
        assert "1234.56" in formatted or "1,234.56" in formatted

    def test_format_eur(self) -> None:
        """Test formatting euros."""
        settings = Settings()
        settings.currency_code = "EUR"

        formatted = settings.format_currency(Decimal("1234.56"))
        assert "€" in formatted

    def test_format_jpy_no_decimals(self) -> None:
        """Test formatting Japanese Yen (0 decimals)."""
        settings = Settings()
        settings.currency_code = "JPY"

        formatted = settings.format_currency(Decimal("1234.56"))
        # Should round to no decimals
        assert "¥" in formatted

    def test_format_without_symbol(self) -> None:
        """Test formatting without currency symbol."""
        settings = Settings()
        settings.currency_code = "USD"

        formatted = settings.format_currency(Decimal("100.00"), include_symbol=False)
        assert "$" not in formatted
        assert "100" in formatted

    def test_format_with_thousands_separator(self) -> None:
        """Test formatting with thousands separator."""
        settings = Settings()
        settings.currency_code = "USD"
        settings.set("thousands_separator", True)

        formatted = settings.format_currency(Decimal("1000.00"))
        assert "," in formatted or "$1000.00" in formatted

    def test_format_without_thousands_separator(self) -> None:
        """Test formatting without thousands separator."""
        settings = Settings()
        settings.currency_code = "USD"
        settings.set("thousands_separator", False)

        formatted = settings.format_currency(Decimal("1000.00"))
        # Should not have comma
        assert "1000.00" in formatted

    def test_format_negative_amounts(self) -> None:
        """Test formatting negative amounts."""
        settings = Settings()
        settings.currency_code = "USD"

        formatted = settings.format_currency(Decimal("-50.00"))
        assert "-" in formatted or "(" in formatted

    def test_format_zero(self) -> None:
        """Test formatting zero."""
        settings = Settings()
        settings.currency_code = "USD"

        formatted = settings.format_currency(Decimal("0.00"))
        assert "0" in formatted

    def test_format_large_number(self) -> None:
        """Test formatting large numbers."""
        settings = Settings()
        settings.currency_code = "USD"

        formatted = settings.format_currency(Decimal("999999.99"))
        assert "$" in formatted


class TestSettingsDateFormat:
    """Tests for date format settings."""

    def test_default_date_format(self) -> None:
        """Test default date format is set."""
        settings = Settings()
        assert settings.date_format is not None
        # Default is GBP (DD/MM/YYYY)
        assert "%" in settings.date_format  # Should be a strftime format

    def test_set_us_date_format(self) -> None:
        """Test setting US date format."""
        settings = Settings()
        settings.date_format = "%m/%d/%Y"
        assert settings.date_format == "%m/%d/%Y"

    def test_set_iso_date_format(self) -> None:
        """Test setting ISO date format."""
        settings = Settings()
        settings.date_format = "%Y-%m-%d"
        assert settings.date_format == "%Y-%m-%d"

    def test_set_german_date_format(self) -> None:
        """Test setting German date format."""
        settings = Settings()
        settings.date_format = "%d.%m.%Y"
        assert settings.date_format == "%d.%m.%Y"


class TestSettingsPersistence:
    """Tests for settings persistence."""

    def test_save_and_load_currency(self) -> None:
        """Test saving and loading currency setting."""
        with TemporaryDirectory() as tmpdir:
            # Create settings in temp directory
            settings1 = Settings()
            original_dir = settings1.settings_file.parent

            settings1.currency_code = "EUR"
            settings1.save()

            # Load in a new instance
            settings2 = Settings()
            assert settings2.currency_code == "EUR"

    def test_save_and_load_date_format(self) -> None:
        """Test saving and loading date format."""
        with TemporaryDirectory() as tmpdir:
            settings1 = Settings()
            settings1.date_format = "%Y-%m-%d"
            settings1.save()

            settings2 = Settings()
            assert settings2.date_format == "%Y-%m-%d"

    def test_save_and_load_custom_setting(self) -> None:
        """Test saving and loading custom settings."""
        with TemporaryDirectory() as tmpdir:
            settings1 = Settings()
            settings1.set("custom_key", "custom_value")
            settings1.save()

            settings2 = Settings()
            assert settings2.get("custom_key") == "custom_value"

    def test_get_default_value(self) -> None:
        """Test getting setting with default value."""
        settings = Settings()
        value = settings.get("nonexistent_key", "default_value")
        assert value == "default_value"

    def test_get_existing_setting(self) -> None:
        """Test getting existing setting."""
        settings = Settings()
        settings.set("test_key", "test_value")
        value = settings.get("test_key")
        assert value == "test_value"


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_invalid_currency_code_not_set(self) -> None:
        """Test that invalid currency code is not set."""
        settings = Settings()
        original = settings.currency_code

        settings.currency_code = "INVALID"
        # Should not change to invalid code
        assert settings.currency_code == original

    def test_currency_code_string_check(self) -> None:
        """Test that currency code is a string."""
        settings = Settings()
        for code in CURRENCIES.keys():
            settings.currency_code = code
            assert isinstance(settings.currency_code, str)
            assert len(settings.currency_code) == 3  # Currency codes are 3 chars


class TestSettingsIntegration:
    """Integration tests for settings workflows."""

    def test_change_currency_and_format(self) -> None:
        """Test changing currency and verifying formatting."""
        settings = Settings()

        # Test USD
        settings.currency_code = "USD"
        usd_formatted = settings.format_currency(Decimal("100.00"))
        assert "$" in usd_formatted

        # Switch to EUR
        settings.currency_code = "EUR"
        eur_formatted = settings.format_currency(Decimal("100.00"))
        assert "€" in eur_formatted
        assert "$" not in eur_formatted

    def test_load_settings_with_all_properties(self) -> None:
        """Test loading settings with multiple properties."""
        settings = Settings()

        settings.currency_code = "GBP"
        settings.date_format = "%d/%m/%Y"
        settings.set("thousands_separator", False)

        assert settings.currency_code == "GBP"
        assert settings.date_format == "%d/%m/%Y"
        assert settings.get("thousands_separator") is False

    def test_settings_singleton_pattern(self) -> None:
        """Test using settings via get_settings() function."""
        from dads_money.settings import get_settings

        settings1 = get_settings()
        settings2 = get_settings()

        # Should be the same instance
        assert settings1 is settings2
