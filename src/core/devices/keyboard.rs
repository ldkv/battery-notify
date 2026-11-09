use std::collections::BTreeMap;
use std::time::Duration;

use super::{DeviceType, Driver, Filter, HidIo, read_reply};

const REPORT_SIZE: usize = 32;
const READ_TIMEOUT: Duration = Duration::from_secs(1);

/// Keychron Link receiver command, works with stock firmware
pub const FR_GET_STATE: u8 = 0xB2;
/// Keyboard command, requires the custom firmware described in docs/keychron-k2-he.md
pub const KC_GET_BATTERY: u8 = 0xA4;

const K2_HE_PIDS: [u16; 3] = [0x0E20, 0x0E21, 0x0E22]; // ANSI, ISO, JIS
const RECEIVER_SLOT_SIZE: usize = 5;
const MAX_BATTERY_LEVEL: u8 = 100;

/// Keychron K2 HE connected via the 2.4 GHz receiver Keychron Link.
/// The keyboard only answers battery requests with the custom firmware described in docs/keychron-k2-he.md.
pub const KEYCHRON_K2_HE: DeviceType = DeviceType {
    name: "Keychron K2 HE",
    vid: 0x3434, // Keychron
    pid: 0xD030, // Keychron Link
    filter: Filter { usage_page: Some(0xFF60), usage: Some(0x61), interface_number: None },
    driver: |_| Box::new(KeychronK2He),
};

/// Some platforms prepend the report ID 0x00 to the received data.
pub fn strip_report_id(report: &[u8], command: u8) -> &[u8] {
    match report {
        [0, second, ..] if *second == command => &report[1..],
        _ => report,
    }
}

/// Parse the reply to `FR_GET_STATE` into {keyboard PID: connected}.
/// Reply: B2 xx, then up to 3 slots of 5 bytes: VID (LE), PID (LE), connected.
pub fn parse_receiver_state(report: &[u8]) -> BTreeMap<u16, bool> {
    let report = strip_report_id(report, FR_GET_STATE);
    let mut devices = BTreeMap::new();
    if report.first() != Some(&FR_GET_STATE) {
        return devices;
    }
    for offset in [2, 7, 12] {
        let Some(slot) = report.get(offset..offset + RECEIVER_SLOT_SIZE) else {
            break;
        };
        let vid = u16::from_le_bytes([slot[0], slot[1]]);
        if vid == 0 {
            continue;
        }
        devices.insert(u16::from_le_bytes([slot[2], slot[3]]), slot[4] != 0);
    }
    devices
}

/// Parse the reply to `KC_GET_BATTERY`, same layout as Keychron/qmk_firmware#477:
/// A4, percentage, voltage in mV (LE, 2 bytes), charging state, transport, model ID.
pub fn parse_battery_report(report: &[u8]) -> Option<u8> {
    match strip_report_id(report, KC_GET_BATTERY) {
        [KC_GET_BATTERY, level, ..] if *level <= MAX_BATTERY_LEVEL => Some(*level),
        _ => None,
    }
}

struct KeychronK2He;

impl KeychronK2He {
    /// Send a command and return the first reply for it, skipping unrelated reports.
    fn request(device: &dyn HidIo, command: u8) -> Vec<u8> {
        let mut message = vec![0; REPORT_SIZE + 1]; // leading report ID 0
        message[1] = command;
        if !device.write(&message) {
            return Vec::new();
        }
        let reply = read_reply(device, REPORT_SIZE + 1, READ_TIMEOUT, |report| {
            strip_report_id(report, command).first() == Some(&command)
        });
        strip_report_id(&reply, command).to_vec()
    }
}

impl Driver for KeychronK2He {
    fn battery_level(&self, device: &dyn HidIo) -> Option<u8> {
        let name = KEYCHRON_K2_HE.name;
        let state = parse_receiver_state(&Self::request(device, FR_GET_STATE));
        let connected = state.iter().any(|(pid, connected)| K2_HE_PIDS.contains(pid) && *connected);
        if !state.is_empty() && !connected {
            tracing::info!("{name} - Not connected to the receiver (asleep or off): {state:?}");
            return None;
        }

        let level = parse_battery_report(&Self::request(device, KC_GET_BATTERY));
        if level.is_none() {
            tracing::warn!("{name} - No battery reply, is the custom firmware flashed? {state:?}");
        }
        level
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::devices::fake::FakeDevice;

    const PADDING: [u8; 20] = [0; 20];
    const BATTERY_LEVEL: u8 = 85;
    const MESSAGE_SIZE: usize = 33; // report ID + 32 bytes

    fn padded(bytes: &[u8]) -> Vec<u8> {
        [bytes, &PADDING].concat()
    }

    // K2 HE ANSI: VID 0x3434, PID 0x0E20, connected, as captured from Keychron Link firmware d.3.1
    fn state_connected() -> Vec<u8> {
        padded(&[0xB2, 0x01, 0x34, 0x34, 0x20, 0x0E, 0x01])
    }

    fn state_disconnected() -> Vec<u8> {
        padded(&[0xB2, 0x01, 0x34, 0x34, 0x20, 0x0E, 0x00])
    }

    // 85%, 3950 mV, on battery, 2.4 GHz, model ID 3
    fn battery_reply() -> Vec<u8> {
        padded(&[0xA4, BATTERY_LEVEL, 0x6E, 0x0F, 0, 0x04, 3])
    }

    #[test]
    fn parse_battery() {
        for (report, expected) in [
            (battery_reply(), Some(85)),
            ([&[0], battery_reply().as_slice()].concat(), Some(85)), // leading report ID
            (vec![0xA4, 100, 0, 0, 2, 1, 3], Some(100)),             // full, over USB
            (vec![0xA4, 0], Some(0)),
            (vec![0xA4, 101, 0, 0], None),
            (vec![0xA4], None),
            (padded(&[0xFF, 0x00]), None), // unknown command reply
            (vec![], None),                // timeout
        ] {
            assert_eq!(parse_battery_report(&report), expected, "{report:?}");
        }
    }

    #[test]
    fn parse_state() {
        let two_keyboards = padded(&[0xB2, 0x01, 0x34, 0x34, 0x20, 0x0E, 0x00, 0x34, 0x34, 0x21, 0x0E, 0x01]);
        for (report, expected) in [
            (state_connected(), vec![(0x0E20, true)]),
            ([&[0], state_connected().as_slice()].concat(), vec![(0x0E20, true)]),
            (state_disconnected(), vec![(0x0E20, false)]),
            (two_keyboards, vec![(0x0E20, false), (0x0E21, true)]),
            (padded(&[0xB2, 0x01]), vec![]), // no paired device
            (battery_reply(), vec![]),
            (vec![], vec![]),
        ] {
            assert_eq!(parse_receiver_state(&report), BTreeMap::from_iter(expected), "{report:?}");
        }
    }

    fn battery_level(replies: Vec<(u8, Vec<Vec<u8>>)>) -> (Option<u8>, FakeDevice) {
        let receiver = FakeDevice::new(1, replies);
        (KeychronK2He.battery_level(&receiver), receiver)
    }

    fn commands(receiver: &FakeDevice) -> Vec<u8> {
        receiver.written.borrow().iter().map(|message| message[1]).collect()
    }

    #[test]
    fn connected() {
        let (level, receiver) =
            battery_level(vec![(FR_GET_STATE, vec![state_connected()]), (KC_GET_BATTERY, vec![battery_reply()])]);
        assert_eq!(level, Some(BATTERY_LEVEL));
        assert_eq!(commands(&receiver), [FR_GET_STATE, KC_GET_BATTERY]);
        assert!(receiver.written.borrow().iter().all(|message| message.len() == MESSAGE_SIZE && message[0] == 0));
    }

    #[test]
    fn skips_unrelated_reports() {
        let notification = padded(&[0xE2, 0x01]);
        let (level, _) = battery_level(vec![
            (FR_GET_STATE, vec![state_connected()]),
            (KC_GET_BATTERY, vec![notification, battery_reply()]),
        ]);
        assert_eq!(level, Some(BATTERY_LEVEL));
    }

    #[test]
    fn keyboard_asleep() {
        let (level, receiver) =
            battery_level(vec![(FR_GET_STATE, vec![state_disconnected()]), (KC_GET_BATTERY, vec![battery_reply()])]);
        assert_eq!(level, None);
        assert_eq!(commands(&receiver), [FR_GET_STATE]);
    }

    #[test]
    fn stock_firmware() {
        let (level, _) = battery_level(vec![(FR_GET_STATE, vec![state_connected()])]);
        assert_eq!(level, None);
    }

    #[test]
    fn without_receiver_state() {
        let (level, _) = battery_level(vec![(KC_GET_BATTERY, vec![battery_reply()])]);
        assert_eq!(level, Some(BATTERY_LEVEL));
    }
}
