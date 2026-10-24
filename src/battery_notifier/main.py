import argparse
import sys

from battery_notifier.logs import configure_logging, logger
from battery_notifier.platforms import current_platform
from battery_notifier.platforms.base import Platform


def main():
    parser = argparse.ArgumentParser(prog="battery-notifier", description="Notify when battery is low")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("settings", help="open the settings dialog")
    args = parser.parse_args()

    configure_logging()
    platform = current_platform()
    if args.command == "settings":
        sys.exit(run_settings_dialog(platform))

    if not platform.acquire_single_instance("BatteryNotifier"):
        logger.info("Already running, exiting")
        return

    # Imported here so that the settings dialog does not load the tray dependencies, and vice versa
    from battery_notifier.ui.tray import TrayApp  # noqa: PLC0415

    TrayApp(platform).run()


def run_settings_dialog(platform: Platform) -> int:
    """Return 0 when the settings were saved."""
    from battery_notifier.core.settings import Settings  # noqa: PLC0415
    from battery_notifier.ui.settings_dialog import SettingsDialog  # noqa: PLC0415

    if not platform.acquire_single_instance("BatteryNotifier.Settings"):
        return 1
    return 0 if SettingsDialog(platform, Settings.load()).run() else 1


if __name__ == "__main__":
    main()
