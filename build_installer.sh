#!/bin/bash
# Build macOS installer for Dad's Money (unsigned version)

set -e

echo "🔨 Building Dad's Money macOS Application..."
echo ""

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run from project root."
    exit 1
fi

source venv/bin/activate

# Install PyInstaller if not present
echo "📦 Checking dependencies..."
pip install -q pyinstaller

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build dist

# Build the .app bundle
echo "🏗️  Building application bundle..."
pyinstaller build_macos.spec --clean --noconfirm

if [ ! -d "dist/DadsMoney.app" ]; then
    echo "❌ Build failed - DadsMoney.app not created"
    exit 1
fi

echo "✅ Application bundle created: dist/DadsMoney.app"
echo ""

# Create installation instructions
echo "📝 Creating installation instructions..."
cat > dist/INSTALLATION_INSTRUCTIONS.txt << 'EOF'
╔════════════════════════════════════════════════════════════════════╗
║              Dad's Money - Installation Instructions              ║
╚════════════════════════════════════════════════════════════════════╝

Thank you for downloading Dad's Money!

This is an UNSIGNED application, which means macOS will require an
extra step on first launch.

═══════════════════════════════════════════════════════════════════
INSTALLATION STEPS
═══════════════════════════════════════════════════════════════════

1. MOVE TO APPLICATIONS
   • Drag "DadsMoney.app" to your Applications folder
   • Or put it anywhere you like

2. FIRST LAUNCH (IMPORTANT!)
   • DO NOT double-click the app yet!
   • RIGHT-CLICK on "DadsMoney.app"
   • Select "Open" from the menu
   • Click "Open" in the security warning dialog
   
   This only needs to be done ONCE!

3. FUTURE LAUNCHES
   • Double-click normally to open
   • No more warnings!

═══════════════════════════════════════════════════════════════════
ALTERNATIVE: REMOVE QUARANTINE FLAG
═══════════════════════════════════════════════════════════════════

If you're comfortable with Terminal:

1. Open Terminal
2. Run this command:
   
   xattr -cr /Applications/DadsMoney.app

3. Double-click to launch normally

═══════════════════════════════════════════════════════════════════
TROUBLESHOOTING
═══════════════════════════════════════════════════════════════════

• "App is damaged and can't be opened"
  → Use the xattr command above, or right-click → Open

• "Developer cannot be verified"
  → This is expected for unsigned apps
  → Right-click → Open to bypass

• App won't launch
  → Check macOS version (requires 10.13+)
  → Make sure you're on Apple Silicon or Intel Mac

═══════════════════════════════════════════════════════════════════
FEATURES
═══════════════════════════════════════════════════════════════════

✓ Microsoft Money 3.0 compatible interface
✓ Multiple account types (Checking, Savings, Credit Card, etc.)
✓ Transaction register with full history
✓ Import/Export QIF, OFX, and CSV files
✓ 20 currency support (GBP, USD, EUR, JPY, and more)
✓ Customizable categories
✓ SQLite database storage

═══════════════════════════════════════════════════════════════════
DATA LOCATION
═══════════════════════════════════════════════════════════════════

Your financial data is stored in:
  ~/Library/Application Support/DadsMoney/

Settings file:
  ~/Library/Application Support/DadsMoney/settings.json

Database:
  ~/Library/Application Support/DadsMoney/dadsmoney.db

═══════════════════════════════════════════════════════════════════
NEED HELP?
═══════════════════════════════════════════════════════════════════

• Check the README.md in the source folder
• Review QUICKSTART.md for usage tips
• See CURRENCY_GUIDE.md for currency settings

═══════════════════════════════════════════════════════════════════

Enjoy using Dad's Money!
Version 0.1.0 - March 2026
EOF

echo "✅ Installation instructions created"
echo ""

# Create DMG if create-dmg is available
if command -v create-dmg &> /dev/null; then
    echo "💿 Creating DMG installer..."
    
    # Remove old DMG if exists
    rm -f dist/DadsMoney-Installer.dmg
    
    create-dmg \
        --volname "Dads Money Installer" \
        --volicon "dist/DadsMoney.app/Contents/Resources/icon-windowed.icns" \
        --window-pos 200 120 \
        --window-size 650 450 \
        --icon-size 100 \
        --icon "DadsMoney.app" 150 150 \
        --hide-extension "DadsMoney.app" \
        --app-drop-link 500 150 \
        --text-size 12 \
        --no-internet-enable \
        "dist/DadsMoney-Installer.dmg" \
        "dist/DadsMoney.app" \
        2>/dev/null || {
            # Fallback to simpler DMG creation
            echo "⚠️  Fancy DMG creation failed, creating basic DMG..."
            hdiutil create -volname "Dads Money" -srcfolder dist/DadsMoney.app -ov -format UDZO dist/DadsMoney-Installer.dmg
        }
    
    # Copy installation instructions to a temporary folder for DMG
    mkdir -p dist/dmg_temp
    cp dist/DadsMoney.app dist/dmg_temp/
    cp dist/INSTALLATION_INSTRUCTIONS.txt dist/dmg_temp/
    
    echo "✅ DMG created: dist/DadsMoney-Installer.dmg"
else
    echo "ℹ️  create-dmg not found. To create fancy DMG:"
    echo "   brew install create-dmg"
    echo ""
    echo "   For now, you can:"
    echo "   • Share dist/DadsMoney.app directly (zip it first)"
    echo "   • Or create basic DMG with: hdiutil create -srcfolder dist/DadsMoney.app dist/DadsMoney.dmg"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ BUILD COMPLETE!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📁 Output files:"
echo "   • Application: dist/DadsMoney.app"
echo "   • Instructions: dist/INSTALLATION_INSTRUCTIONS.txt"

if [ -f "dist/DadsMoney-Installer.dmg" ]; then
    echo "   • DMG Installer: dist/DadsMoney-Installer.dmg"
    FILESIZE=$(du -h "dist/DadsMoney-Installer.dmg" | cut -f1)
    echo "     Size: $FILESIZE"
fi

echo ""
echo "🧪 To test locally:"
echo "   open dist/DadsMoney.app"
echo ""
echo "📦 To distribute:"
echo "   1. Zip the app:"
echo "      cd dist && zip -r DadsMoney.zip DadsMoney.app INSTALLATION_INSTRUCTIONS.txt"
echo "   2. Share DadsMoney.zip or DadsMoney-Installer.dmg"
echo ""
echo "📝 Recipients should:"
echo "   • Read INSTALLATION_INSTRUCTIONS.txt"
echo "   • RIGHT-CLICK → Open on first launch"
echo ""
echo "═══════════════════════════════════════════════════════════════"
