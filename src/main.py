import sys

from PyQt6.QtWidgets import QApplication

from scanner import ScannerWidget

def main() -> None:
    """Create the GUI"""

    app = QApplication(sys.argv)

    window = ScannerWidget()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
