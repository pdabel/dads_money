"""Test script for settings functionality."""

from dads_money.settings import get_settings, CURRENCIES


def test_settings():
    """Test the settings module."""
    
    print("=" * 60)
    print("Dad's Money - Settings Test")
    print("=" * 60)
    print()
    
    # Get settings instance
    settings = get_settings()
    
    print("1. Default Settings")
    print(f"   Currency: {settings.currency_code} - {settings.currency_name}")
    print(f"   Symbol: {settings.currency_symbol}")
    print(f"   Decimal places: {settings.decimal_places}")
    print(f"   Date format: {settings.date_format}")
    print()
    
    # Test currency formatting
    print("2. Currency Formatting (USD)")
    amounts = [100, 1234.56, -500.25, 1000000]
    for amount in amounts:
        formatted = settings.format_currency(amount)
        print(f"   {amount:>12} → {formatted}")
    print()
    
    # Test different currencies
    print("3. Different Currencies")
    test_amount = 1234.56
    for code in ["USD", "EUR", "GBP", "JPY", "CAD", "INR", "CHF"]:
        settings.currency_code = code
        formatted = settings.format_currency(test_amount)
        print(f"   {code}: {formatted:>15} ({settings.currency_name})")
    print()
    
    # Reset to USD
    settings.currency_code = "USD"
    
    # Test thousands separator toggle
    print("4. Thousands Separator")
    settings.set("thousands_separator", True)
    print(f"   With separator:    {settings.format_currency(1234567.89)}")
    settings.set("thousands_separator", False)
    print(f"   Without separator: {settings.format_currency(1234567.89)}")
    settings.set("thousands_separator", True)  # Reset
    print()
    
    # Test date formats
    print("5. Date Formats")
    from datetime import date
    test_date = date(2026, 3, 15)
    date_formats = [
        ("%m/%d/%Y", "US format"),
        ("%d/%m/%Y", "UK format"),
        ("%Y-%m-%d", "ISO format"),
        ("%d.%m.%Y", "German format"),
    ]
    for fmt, label in date_formats:
        formatted = test_date.strftime(fmt)
        print(f"   {label:15} {fmt:12} → {formatted}")
    print()
    
    # Show all available currencies
    print("6. All Available Currencies")
    print(f"   Total: {len(CURRENCIES)} currencies")
    for code, info in sorted(CURRENCIES.items()):
        print(f"   {code}: {info['symbol']:>4} - {info['name']:<25} ({info['decimal_places']} decimals)")
    print()
    
    # Test settings persistence
    print("7. Testing Save/Load")
    print(f"   Settings file: {settings.settings_file}")
    settings.currency_code = "EUR"
    settings.date_format = "%d/%m/%Y"
    settings.save()
    print("   ✓ Settings saved")
    
    # Create new instance to test loading
    from dads_money.settings import Settings
    new_settings = Settings()
    print(f"   ✓ Settings loaded")
    print(f"   Currency: {new_settings.currency_code}")
    print(f"   Date format: {new_settings.date_format}")
    
    # Reset to defaults
    settings.currency_code = "USD"
    settings.date_format = "%m/%d/%Y"
    settings.save()
    print("   ✓ Reset to defaults")
    print()
    
    print("=" * 60)
    print("Settings Test Complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_settings()
