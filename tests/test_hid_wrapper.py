from battery_notifier.core.devices import hid_wrapper
from battery_notifier.core.devices.hid_wrapper import DeviceInfo, HIDWrapper

RAW_DEVICES = [
    {"path": b"keyboard", "vendor_id": 0x3434, "product_id": 0xD030, "usage_page": 0x01, "usage": 0x06},
    {"path": b"raw_hid", "vendor_id": 0x3434, "product_id": 0xD030, "usage_page": 0xFF60, "usage": 0x61},
]


def test_enumerate_only_opens_matching_devices(monkeypatch):
    opened = []
    monkeypatch.setattr(hid_wrapper.hid, "enumerate", lambda vid, pid: [dict(device) for device in RAW_DEVICES])
    monkeypatch.setattr(HIDWrapper, "__init__", lambda self, path=None: opened.append(path) or None)
    monkeypatch.setattr(HIDWrapper, "__bool__", lambda self: True)
    monkeypatch.setattr(HIDWrapper, "__del__", lambda self: None)
    monkeypatch.setattr(HIDWrapper, "get_report_descriptor", lambda self: "06 60 FF")

    devices = HIDWrapper.enumerate_matching_devices(0x3434, 0xD030, DeviceInfo(usage_page=0xFF60, usage=0x61))

    assert opened == [b"raw_hid"]
    assert [device.path for device in devices] == [b"raw_hid"]
    assert devices[0].report_descriptor == "06 60 FF"
