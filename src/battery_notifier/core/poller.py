import json

from battery_notifier.core.paths import seen_devices_file
from battery_notifier.core.providers import BatteryProvider, BatteryReading, HIDProvider
from battery_notifier.core.settings import Settings
from battery_notifier.logs import logger


class Poller:
    def __init__(self, providers: list[BatteryProvider]):
        self._providers = providers

    def poll(self, settings: Settings) -> list[BatteryReading]:
        readings = [reading for provider in self._providers for reading in provider.read(settings)]
        remember_devices({reading.name for reading in readings})
        return readings


def load_seen_devices() -> set[str]:
    try:
        return set(json.loads(seen_devices_file().read_text(encoding="utf-8")))
    except OSError, ValueError, TypeError:
        return set()


def remember_devices(names: set[str]):
    """Keep the name of every device ever seen, so the settings dialog can list them while disconnected."""
    seen = load_seen_devices()
    if names <= seen:
        return
    try:
        seen_devices_file().write_text(json.dumps(sorted(seen | names)), encoding="utf-8")
    except OSError as e:
        logger.warning(f"Could not save seen devices: {e}")


def known_device_names(settings: Settings) -> list[str]:
    return sorted(set(HIDProvider.device_names()) | load_seen_devices() | settings.disabled_devices)
