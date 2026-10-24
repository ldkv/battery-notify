import sys


def is_frozen() -> bool:
    """True when running from the standalone executable."""
    return getattr(sys, "frozen", False)


def app_command(*args: str) -> list[str]:
    """Command line to start this app again, e.g. to open the settings dialog in its own process."""
    if is_frozen():
        return [sys.executable, *args]
    return [sys.executable, "-m", "battery_notifier", *args]
