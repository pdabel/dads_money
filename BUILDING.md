# Building Dad's Money for macOS

This guide explains how to build a standalone macOS application bundle for Dad's Money.

## Quick Build (Unsigned)

```bash
chmod +x build_installer.sh
./build_installer.sh
```

**Output:**
- `dist/DadsMoney.app` - macOS application bundle
- `dist/INSTALLATION_INSTRUCTIONS.txt` - User guide
- `dist/DadsMoney-Installer.dmg` - DMG installer (if `create-dmg` installed)

## Requirements

- **macOS**: 10.13 (High Sierra) or later
- **Python**: 3.10+ (already in your venv)
- **PyInstaller**: Auto-installed by build script
- **Optional**: `create-dmg` for DMG creation

### Install create-dmg (Optional)

```bash
brew install create-dmg
```

## Build Process

The build script:

1. ✅ Activates virtual environment
2. ✅ Installs PyInstaller
3. ✅ Cleans previous builds
4. ✅ Bundles Python + dependencies into .app
5. ✅ Creates installation instructions
6. ✅ Creates DMG installer (if available)

## Distribution

### Option 1: Share the .app (Recommended)

```bash
cd dist
zip -r DadsMoney.zip DadsMoney.app INSTALLATION_INSTRUCTIONS.txt
```

Recipients:
- Extract the zip
- Drag `DadsMoney.app` to Applications
- **Right-click → Open** on first launch
- Double-click normally after that

### Option 2: Share the DMG

If you have `create-dmg` installed:
- Share `dist/DadsMoney-Installer.dmg`
- Users double-click DMG
- Drag app to Applications
- **Right-click → Open** on first launch

## Why "Right-Click → Open"?

This app is **unsigned** (no Apple Developer account needed). macOS Gatekeeper requires:
- **First launch**: Right-click → Open → Click "Open" button
- **After that**: Normal double-click works

This is a one-time step and perfectly safe for personal distribution.

## Testing Locally

```bash
# Test the built app
open dist/DadsMoney.app

# If you get security warning
xattr -cr dist/DadsMoney.app
open dist/DadsMoney.app
```

## File Sizes

Typical sizes:
- **DadsMoney.app**: ~100-120 MB (includes Python + Qt)
- **DadsMoney.zip**: ~40-50 MB (compressed)
- **DadsMoney-Installer.dmg**: ~45-55 MB

This is normal for PyInstaller apps - they include the entire Python runtime and all dependencies.

## What Gets Bundled

The .app includes:
- ✅ Python 3.x runtime
- ✅ PySide6 (Qt6) framework
- ✅ All Dad's Money code
- ✅ SQLite (built into Python)
- ✅ ofxparse, dateutil libraries

Users **don't need**:
- ❌ Python installed
- ❌ Virtual environment
- ❌ Any dependencies
- ❌ Terminal/command line

## Troubleshooting

### "App is damaged and can't be opened"

```bash
xattr -cr /Applications/DadsMoney.app
```

This removes the quarantine flag macOS adds to downloaded apps.

### PyInstaller fails to install

```bash
source venv/bin/activate
pip install --upgrade pip
pip install pyinstaller
```

### App crashes on launch

Check Console.app for errors. Common issues:
- Missing hidden imports → Add to `build_macos.spec`
- Qt plugin issues → Usually resolved automatically
- Python version mismatch → Rebuild with same Python version

### Large file size

This is normal. To reduce:
- **UPX compression**: Already enabled in spec file
- **Exclude packages**: Edit `build_macos.spec` excludes
- Trade-off: Can't reduce much without breaking functionality

## Advanced: Code Signing (Optional)

If you get an Apple Developer account ($99/year):

1. **Find your signing identity**:
   ```bash
   security find-identity -v -p codesigning
   ```

2. **Sign the app**:
   ```bash
   codesign --deep --force --verify --verbose \
       --sign "Developer ID Application: Your Name (TEAMID)" \
       --options runtime \
       --entitlements entitlements.plist \
       dist/DadsMoney.app
   ```

3. **Verify**:
   ```bash
   codesign --verify --verbose dist/DadsMoney.app
   spctl -a -v dist/DadsMoney.app
   ```

## Customization

### Add an App Icon

1. Create `icon.icns` (512x512 PNG → icns)
2. Edit `build_macos.spec`:
   ```python
   icon='icon.icns',
   ```
3. Rebuild

### Change App Info

Edit `build_macos.spec` info_plist section:
- Version numbers
- Copyright
- Display name
- Bundle identifier

## Platform Compatibility

**Supported macOS versions:**
- ✅ macOS 10.13 (High Sierra) - 2017
- ✅ macOS 10.14 (Mojave) - 2018
- ✅ macOS 10.15 (Catalina) - 2019
- ✅ macOS 11 (Big Sur) - 2020
- ✅ macOS 12 (Monterey) - 2021
- ✅ macOS 13 (Ventura) - 2022
- ✅ macOS 14 (Sonoma) - 2023
- ✅ macOS 15+ (Future versions)

**Architecture:**
- ✅ Intel (x86_64)
- ✅ Apple Silicon (arm64) - if built on Apple Silicon
- ⚠️ Universal binary: Requires building on both architectures

## Continuous Integration

For automated builds, add to CI:

```yaml
# .github/workflows/build.yml
- name: Build macOS app
  run: |
    source venv/bin/activate
    pip install pyinstaller
    pyinstaller build_macos.spec --clean
```

## Summary

✅ **For family/friends**: Build unsigned, share with instructions  
✅ **For personal use**: Build and use locally  
✅ **For public release**: Consider Apple Developer account + signing  
✅ **Easy distribution**: Zip the .app or share DMG

The build process is straightforward and the resulting app works on any Mac without Python installed!
