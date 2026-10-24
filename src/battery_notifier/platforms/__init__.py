import sys
from functools import cache

from battery_notifier.platforms.base import Platform


@cache
def current_platform() -> Platform:
    if sys.platform == "win32":
        from battery_notifier.platforms.windows import WindowsPlatform  # noqa: PLC0415

        return WindowsPlatform()
    return Platform()
