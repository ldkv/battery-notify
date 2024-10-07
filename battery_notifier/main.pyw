import threading

from battery_notifier.logs import configure_logging
from battery_notifier.system_tray import battery_loop, initialize_system_tray

if __name__ == "__main__":
    configure_logging()
    system_tray = initialize_system_tray()
    thread = threading.Thread(target=battery_loop, args=[system_tray], daemon=True)
    thread.start()
    system_tray.run()
