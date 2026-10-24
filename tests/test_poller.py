import pytest

from battery_notifier.core import poller
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


def test_os_provider_skips_disabled_and_unknown_levels():
    provider = OSProvider(lambda: [("Earbuds", 70), ("Speaker", -1), ("Keyboard", 40)])
    readings = provider.read(Settings(disabled_devices=frozenset({"Keyboard"})))
    assert readings == [BatteryReading("Earbuds", 70)]


def test_hid_provider_does_not_open_disabled_devices(monkeypatch):
    provider = HIDProvider()
    monkeypatch.setattr(provider, "_find", lambda device_class: pytest.fail(f"opened {device_class.name}"))
    assert provider.read(Settings(disabled_devices=frozenset(HIDProvider.device_names()))) == []
