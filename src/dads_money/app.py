"""Main application entry point."""

import sys
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QApplication

from .ui import MainWindow


def main(db_path: Optional[Path] = None):
    """Launch the Dad's Money application.

    Args:
        db_path: Optional path to database file. If None, uses default location.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Dad's Money")
    app.setOrganizationName("DadsMoney")

    window = MainWindow(db_path=db_path)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
