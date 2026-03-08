#!/usr/bin/env python3
"""Quick launcher script for Dad's Money.

Usage:
    python run.py           # Launch the application
    
Or activate venv first:
    source venv/bin/activate
    python run.py
"""

if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    # Add src to path
    src_path = Path(__file__).parent / "src"
    sys.path.insert(0, str(src_path))
    
    try:
        from dads_money.app import main
        main()
    except ImportError as e:
        print("ERROR: Dependencies not installed!")
        print(f"Details: {e}")
        print("\nPlease run:")
        print("  source venv/bin/activate")
        print("  pip install -e .")
        sys.exit(1)
