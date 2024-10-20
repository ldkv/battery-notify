"""PySide6 port of the bluetooth/btscanner example from Qt v6.x"""

import sys

from device import DeviceDiscoveryDialog
from PySide6.QtWidgets import QApplication

if __name__ == "__main__":
    app = QApplication(sys.argv)
    d = DeviceDiscoveryDialog()
    d.exec()
    sys.exit(0)
