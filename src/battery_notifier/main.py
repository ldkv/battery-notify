import threading

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from battery_notifier.logs import configure_logging
from battery_notifier.system_tray import device_loop, initialize_system_tray

app = QApplication([])
app.setQuitOnLastWindowClosed(False)

# Create the icon
icon = QIcon("icon.png")

# Create the tray
tray = QSystemTrayIcon()
tray.setIcon(icon)
tray.setVisible(True)

# Create the menu
menu = QMenu()
action = QAction("A menu item")
menu.addAction(action)

# Add a Quit option to the menu.
quit = QAction("Quit")
quit.triggered.connect(app.quit)
menu.addAction(quit)

# Add the menu to the tray
tray.setContextMenu(menu)


def main():
    configure_logging()
    system_tray = initialize_system_tray()
    thread = threading.Thread(name="device_loop", target=device_loop, args=[system_tray], daemon=True)
    thread.start()
    system_tray.run()


if __name__ == "__main__":
    main()
