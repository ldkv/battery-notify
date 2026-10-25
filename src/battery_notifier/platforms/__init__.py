import sys
from functools import cache

from battery_notifier.platforms.base import Platform


@cache
def current_platform() -> Platform:
    if sys.platform == "win32":
        from battery_notifier.platforms.windows import WindowsPlatform  # noqa: PLC0415

        return WindowsPlatform()
    if sys.platform == "darwin":
        from battery_notifier.platforms.macos import MacOSPlatform  # noqa: PLC0415

        return MacOSPlatform()
    return Platform()
