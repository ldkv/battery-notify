import threading

from battery_notifier.logs import configure_logging
from battery_notifier.system_tray import device_loop, initialize_system_tray


def main():
    configure_logging()
    system_tray = initialize_system_tray()
    thread = threading.Thread(name="device_loop", target=device_loop, args=[system_tray], daemon=True)
    thread.start()
    system_tray.run()


if __name__ == "__main__":
    main()
