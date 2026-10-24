import pytest

from battery_notifier.configs import DEFAULT_BATTERY_LEVEL
from battery_notifier.core.devices.hid_wrapper import HIDWrapper
from battery_notifier.core.devices.mouse import M6_REPORT_SIZE, KeychronM6, parse_m6_battery_report

BATTERY_LEVEL = 22
# Reply to B3 06 as captured from Keychron Ultra-Link 8K firmware 1.06: 22%, on battery
BATTERY_REPLY = list(
    bytes.fromhex(
        "B4 06 00 22 22 02 90 01 20 03 E8 03 DC 05 B8 0B 15 05 04 0A 16 00 00 00 00 00 00 B7 00 00 00 04 "
        "14 04 04 04 04 04 04 04 04 00 00 00 00 01 02 03 04 05 06 05 00 00 06 00 00 00 00 00 00 00 00 00"
    )
)


def with_battery(byte: int) -> list[int]:
    return BATTERY_REPLY[:20] + [byte] + BATTERY_REPLY[21:]


@pytest.mark.parametrize(
    "report, expected",
    [
        (BATTERY_REPLY, BATTERY_LEVEL),
        (with_battery(0xE4), 100),  # charging
        (with_battery(0x00), 0),
        (with_battery(0x65), DEFAULT_BATTERY_LEVEL),
        (BATTERY_REPLY[:20], DEFAULT_BATTERY_LEVEL),  # truncated
        ([0xB4, 0x07] + BATTERY_REPLY[2:], DEFAULT_BATTERY_LEVEL),  # other command
        ([0xE2, 0x01, 0x01, 0x00, 0x16] + [0] * 59, DEFAULT_BATTERY_LEVEL),  # status notification
        ([], DEFAULT_BATTERY_LEVEL),  # timeout
    ],
)
def test_parse_m6_battery_report(report, expected):
    assert parse_m6_battery_report(report) == expected


class FakeReceiver(HIDWrapper):
    """Replies to the written message with the given reports, in order."""

    def __init__(self, replies: list[list[int]]):
        super().__init__()
        self.replies = replies
        self.written: list[list[int]] = []

    def write(self, message: list[int] | None) -> bool:
        assert message is not None
        self.written.append(message)
        return True

    def read(self, size: int, timeout_ms: int) -> list[int]:
        return self.replies.pop(0)[:size] if self.replies else []


def get_battery_level(replies: list[list[int]]) -> tuple[int, FakeReceiver]:
    receiver = FakeReceiver(replies)
    mouse = KeychronM6.__new__(KeychronM6)  # skip device discovery
    mouse.name = "Keychron M6"
    return mouse.get_battery_level(receiver), receiver


def test_get_battery_level():
    battery_level, receiver = get_battery_level([BATTERY_REPLY])
    assert battery_level == BATTERY_LEVEL
    assert receiver.written == [[0xB3, 0x06] + [0] * (M6_REPORT_SIZE - 2)]


def test_get_battery_level_skips_unrelated_reports():
    notification = [0xE2, 0x01, 0x01, 0x00, 0x16] + [0] * 59
    battery_level, _ = get_battery_level([notification, BATTERY_REPLY])
    assert battery_level == BATTERY_LEVEL


def test_get_battery_level_mouse_asleep():
    battery_level, _ = get_battery_level([])
    assert battery_level == DEFAULT_BATTERY_LEVEL
