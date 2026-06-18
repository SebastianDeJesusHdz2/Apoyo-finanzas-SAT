import sys

from PySide6.QtWidgets import QApplication

from pfinanzas.core.db import ReceiptStore, init_db
from pfinanzas.core.paths import ensure_app_dirs
from pfinanzas.ui.main_window import FinanceWindow


def main() -> int:
    ensure_app_dirs()
    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("PFinanzas")
    app.setOrganizationName("Local")

    window = FinanceWindow(ReceiptStore())
    window.resize(1320, 820)
    window.show()

    return app.exec()
