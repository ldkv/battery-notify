import pytest

from battery_notifier.configs import DEFAULT_BATTERY_LEVEL
from battery_notifier.devices.keyboard import (
    FR_GET_STATE,
    KC_GET_BATTERY,
    KeychronK2HE,
    parse_battery_report,
    parse_receiver_state,
)

PADDING = [0] * 20
# K2 HE ANSI: VID 0x3434, PID 0x0E20, connected, as captured from Keychron Link firmware d.3.1
STATE_CONNECTED = [0xB2, 0x01, 0x34, 0x34, 0x20, 0x0E, 0x01] + PADDING
STATE_DISCONNECTED = [0xB2, 0x01, 0x34, 0x34, 0x20, 0x0E, 0x00] + PADDING
# 85%, 3950 mV, on battery, 2.4 GHz, model ID 3
BATTERY_LEVEL = 85
BATTERY_REPLY = [0xA4, BATTERY_LEVEL, 0x6E, 0x0F, 0, 0x04, 3] + PADDING
MESSAGE_SIZE = 33  # report ID + 32 bytes


@pytest.mark.parametrize(
    "report, expected",
    [
        (BATTERY_REPLY, 85),
        ([0] + BATTERY_REPLY, 85),  # leading report ID
        ([0xA4, 100, 0, 0, 2, 1, 3], 100),  # full, over USB
        ([0xA4, 0], 0),
        ([0xA4, 101, 0, 0], DEFAULT_BATTERY_LEVEL),
        ([0xA4], DEFAULT_BATTERY_LEVEL),
        ([0xFF, 0x00] + PADDING, DEFAULT_BATTERY_LEVEL),  # unknown command reply
        ([], DEFAULT_BATTERY_LEVEL),  # timeout
    ],
)
def test_parse_battery_report(report, expected):
    assert parse_battery_report(report) == expected


@pytest.mark.parametrize(
    "report, expected",
    [
        (STATE_CONNECTED, {0x0E20: True}),
        ([0] + STATE_CONNECTED, {0x0E20: True}),
        (STATE_DISCONNECTED, {0x0E20: False}),
        (
            [0xB2, 0x01] + [0x34, 0x34, 0x20, 0x0E, 0x00] + [0x34, 0x34, 0x21, 0x0E, 0x01] + PADDING,
            {0x0E20: False, 0x0E21: True},
        ),
        ([0xB2, 0x01] + PADDING, {}),  # no paired device
        (BATTERY_REPLY, {}),
        ([], {}),
    ],
)
def test_parse_receiver_state(report, expected):
    assert parse_receiver_state(report) == expected


class FakeReceiver:
    """Replies to each written command with the given reports, in order."""

    def __init__(self, replies: dict[int, list[list[int]]]):
        self.replies = replies
        self.pending: list[list[int]] = []
        self.written: list[list[int]] = []

    def write(self, message: list[int]) -> bool:
        self.written.append(message)
        self.pending = list(self.replies.get(message[1], []))
        return True

    def read(self, size: int, timeout_ms: int) -> list[int]:
        return self.pending.pop(0)[:size] if self.pending else []


def get_battery_level(replies: dict[int, list[list[int]]]) -> tuple[int, FakeReceiver]:
    receiver = FakeReceiver(replies)
    keyboard = KeychronK2HE.__new__(KeychronK2HE)  # skip device discovery
    keyboard.name = "Keychron K2 HE"
    return keyboard.get_battery_level(receiver), receiver  # type: ignore[arg-type]


def test_get_battery_level_connected():
    battery_level, receiver = get_battery_level({FR_GET_STATE: [STATE_CONNECTED], KC_GET_BATTERY: [BATTERY_REPLY]})
    assert battery_level == BATTERY_LEVEL
    assert [message[1] for message in receiver.written] == [FR_GET_STATE, KC_GET_BATTERY]
    assert all(len(message) == MESSAGE_SIZE and message[0] == 0 for message in receiver.written)


def test_get_battery_level_skips_unrelated_reports():
    notification = [0xE2, 0x01] + PADDING
    battery_level, _ = get_battery_level(
        {FR_GET_STATE: [STATE_CONNECTED], KC_GET_BATTERY: [notification, BATTERY_REPLY]}
    )
    assert battery_level == BATTERY_LEVEL


def test_get_battery_level_keyboard_asleep():
    battery_level, receiver = get_battery_level({FR_GET_STATE: [STATE_DISCONNECTED], KC_GET_BATTERY: [BATTERY_REPLY]})
    assert battery_level == DEFAULT_BATTERY_LEVEL
    assert [message[1] for message in receiver.written] == [FR_GET_STATE]


def test_get_battery_level_stock_firmware():
    battery_level, _ = get_battery_level({FR_GET_STATE: [STATE_CONNECTED]})
    assert battery_level == DEFAULT_BATTERY_LEVEL


def test_get_battery_level_without_receiver_state():
    battery_level, _ = get_battery_level({KC_GET_BATTERY: [BATTERY_REPLY]})
    assert battery_level == BATTERY_LEVEL
