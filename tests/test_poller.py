import pytest

from battery_notifier.configs import DEFAULT_BATTERY_LEVEL
from battery_notifier.core import poller, providers
from battery_notifier.core.poller import Poller, known_device_names, load_seen_devices
from battery_notifier.core.providers import BatteryReading, HIDProvider, OSProvider
from battery_notifier.core.settings import Settings


@pytest.fixture(autouse=True)
def seen_devices_file(tmp_path, monkeypatch):
    path = tmp_path / "seen_devices.json"
    monkeypatch.setattr(poller, "seen_devices_file", lambda: path)
    return path


class FakeProvider:
    def __init__(self, readings: list[BatteryReading]):
        self.readings = readings

    def read(self, settings: Settings) -> list[BatteryReading]:
        return self.readings


def test_poll_merges_providers_and_remembers_devices():
    mouse, headset = BatteryReading("Mouse", 50), BatteryReading("Headset", None)
    readings = Poller([FakeProvider([mouse]), FakeProvider([headset])]).poll(Settings())

    assert readings == [mouse, headset]
    assert load_seen_devices() == {"Mouse", "Headset"}


def test_seen_devices_are_kept_while_disconnected():
    Poller([FakeProvider([BatteryReading("Mouse", 50)])]).poll(Settings())
    Poller([FakeProvider([BatteryReading("Headset", 80)])]).poll(Settings())
    assert load_seen_devices() == {"Mouse", "Headset"}


def test_known_device_names(seen_devices_file):
    seen_devices_file.write_text('["Earbuds"]')
    names = known_device_names(Settings(disabled_devices=frozenset({"Old speaker"})))
    assert set(names) == {*HIDProvider.device_names(), "Earbuds", "Old speaker"}
    assert names == sorted(names)


def test_corrupted_seen_devices_file(seen_devices_file):
    seen_devices_file.write_text("{")
    assert load_seen_devices() == set()


def test_os_provider_skips_disabled_devices():
    provider = OSProvider(lambda: [("Earbuds", 70), ("Keyboard", 40)])
    readings = provider.read(Settings(disabled_devices=frozenset({"Keyboard"})))
    assert readings == [BatteryReading("Earbuds", 70)]


def test_hid_provider_does_not_open_disabled_devices(monkeypatch):
    provider = HIDProvider()
    monkeypatch.setattr(provider, "_find", lambda device_class: pytest.fail(f"opened {device_class.name}"))
    assert provider.read(Settings(disabled_devices=frozenset(HIDProvider.device_names()))) == []


def fake_device_class(levels_per_instance: list[list[int]]):
    """A device type whose n-th instance, i.e. n-th search, answers the n-th list of levels in turn."""
    instances = iter(levels_per_instance)

    class FakeMouse:
        name = "Fake mouse"

        def __init__(self):
            try:
                self.levels = iter(next(instances))
            except StopIteration:
                raise LookupError("Device not found: Fake mouse") from None

        def update_battery_level(self) -> int:
            return next(self.levels)

    return FakeMouse


def test_hid_provider_searches_again_a_device_that_stopped_answering(monkeypatch):
    """After the computer slept, the device comes back under a new path: the stored one fails."""
    monkeypatch.setattr(providers, "HID_DEVICES", [fake_device_class([[80, DEFAULT_BATTERY_LEVEL], [42]])])
    provider = HIDProvider()
    assert provider.read(Settings()) == [BatteryReading("Fake mouse", 80)]
    assert provider.read(Settings()) == [BatteryReading("Fake mouse", 42)]


def test_hid_provider_drops_a_device_no_longer_found(monkeypatch):
    monkeypatch.setattr(providers, "HID_DEVICES", [fake_device_class([[80, DEFAULT_BATTERY_LEVEL]])])
    provider = HIDProvider()
    assert provider.read(Settings()) == [BatteryReading("Fake mouse", 80)]
    assert provider.read(Settings()) == []


def test_hid_provider_shows_a_found_device_that_does_not_answer(monkeypatch):
    """E.g. a receiver whose keyboard is asleep: found again, still without a level."""
    monkeypatch.setattr(
        providers, "HID_DEVICES", [fake_device_class([[DEFAULT_BATTERY_LEVEL], [DEFAULT_BATTERY_LEVEL]])]
    )
    assert HIDProvider().read(Settings()) == [BatteryReading("Fake mouse", None)]
