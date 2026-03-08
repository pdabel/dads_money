"""Main application entry point."""

import sys
from PySide6.QtWidgets import QApplication

from .ui import MainWindow


def main():
    """Launch the Dad's Money application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Dad's Money")
    app.setOrganizationName("DadsMoney")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
