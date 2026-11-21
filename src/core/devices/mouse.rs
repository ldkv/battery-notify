use std::borrow::Cow;
use std::thread;
use std::time::Duration;

use super::{DeviceType, Driver, Filter, HidIo, read_reply};

pub const RAZER_PRO_CLICK_MINI: DeviceType = DeviceType {
    name: Cow::Borrowed("Razer Pro Click Mini"),
    vid: 0x1532,
    pid: 0x009A,
    filter: Filter { interface_number: Some(0), ..Filter::ANY },
    driver: |_| Box::new(RazerProClickMini),
};

const RAZER_MESSAGE_SIZE: usize = 91;
const RAZER_REPORT_ID: u8 = 0;
const RAZER_BATTERY_INDEX: usize = 10;

struct RazerProClickMini;

impl RazerProClickMini {
    fn battery_message() -> Vec<u8> {
        let mut message = vec![0; RAZER_MESSAGE_SIZE];
        message[..9].copy_from_slice(&[
            RAZER_REPORT_ID,
            0,    // status
            0x1F, // transaction_id
            0,    // remaining packets
            0,    // remaining packets
            0,    // protocol_type
            0x02, // command_class
            0x07, // command_id
            0x80, // data_size
        ]);
        message[RAZER_MESSAGE_SIZE - 2] = 0x85; // crc
        message
    }
}

impl Driver for RazerProClickMini {
    fn battery_level(&self, device: &dyn HidIo) -> Option<u8> {
        if !device.send_feature_report(&Self::battery_message()) {
            return None;
        }
        thread::sleep(Duration::from_millis(400));
        let report = device.get_feature_report(RAZER_REPORT_ID, RAZER_MESSAGE_SIZE);
        // Battery level is a value between 0 and 255
        let battery_255 = u16::from(*report.get(RAZER_BATTERY_INDEX)?);
        u8::try_from(battery_255 * 100 / 255).ok()
    }
}

// Keychron 8K mouse protocol, as used by Keychron Launcher
const M6_REPORT_SIZE: usize = 64; // report ID + 63 bytes
const M6_READ_TIMEOUT: Duration = Duration::from_secs(1);
const M6_REQUEST_ID: u8 = 0xB3;
const M6_REPLY_ID: u8 = 0xB4;
const M6_GET_INFO: u8 = 0x06;
const M6_BATTERY_INDEX: usize = 20; // after report ID and command
const M6_PERCENTAGE_MASK: u8 = 0x7F; // bit 7 is the charging state
const MAX_BATTERY_LEVEL: u8 = 100;

/// Keychron M6 8K connected via the 2.4 GHz receiver Keychron Ultra-Link 8K, with stock firmware.
pub const KEYCHRON_M6: DeviceType = DeviceType {
    name: Cow::Borrowed("Keychron M6"),
    vid: 0x3434, // Keychron
    pid: 0xD028, // Keychron Ultra-Link 8K
    filter: Filter { usage_page: Some(0xFFC1), usage: Some(0x01), interface_number: None },
    driver: |_| Box::new(KeychronM6),
};

/// Parse the reply to `M6_GET_INFO`: B4 06 ..., battery at index 20, percentage in bits 0-6.
pub fn parse_m6_battery_report(report: &[u8]) -> Option<u8> {
    if report.len() <= M6_BATTERY_INDEX || report[..2] != [M6_REPLY_ID, M6_GET_INFO] {
        return None;
    }
    Some(report[M6_BATTERY_INDEX] & M6_PERCENTAGE_MASK).filter(|level| *level <= MAX_BATTERY_LEVEL)
}

struct KeychronM6;

impl Driver for KeychronM6 {
    fn battery_level(&self, device: &dyn HidIo) -> Option<u8> {
        let mut message = vec![0; M6_REPORT_SIZE];
        message[..2].copy_from_slice(&[M6_REQUEST_ID, M6_GET_INFO]);
        if !device.write(&message) {
            return None;
        }

        // Skip unrelated reports, e.g. the receiver's E2 status notifications
        let reply = read_reply(device, M6_REPORT_SIZE + 1, M6_READ_TIMEOUT, |report| {
            report.starts_with(&[M6_REPLY_ID, M6_GET_INFO])
        });
        if reply.is_empty() {
            tracing::info!("{} - No battery reply (asleep, off or charging?)", KEYCHRON_M6.name);
        }
        parse_m6_battery_report(&reply)
    }
}

// Logitech HID++ 2.0, long reports
const HIDPP_LONG_REPORT_ID: u8 = 0x11;
const HIDPP_REPORT_SIZE: usize = 20; // report ID + 19 bytes
const HIDPP_READ_TIMEOUT: Duration = Duration::from_secs(1);
const HIDPP_RECEIVER_SLOT: u8 = 1; // first device paired to the receiver
const HIDPP_ERROR: u8 = 0xFF;
const HIDPP_SOFTWARE_ID: u8 = 0x0A; // tells our replies apart from notifications and other apps'
const HIDPP_ROOT: u8 = 0x00; // IRoot is always at feature index 0
const HIDPP_GET_FEATURE: u8 = 0x00;
const HIDPP_UNIFIED_BATTERY: u16 = 0x1004;
const HIDPP_GET_STATUS: u8 = 0x01;

/// Logitech PRO X3 SUPERSTRIKE connected via its Lightspeed receiver.
pub const LOGITECH_PRO_X3_SUPERSTRIKE: DeviceType = DeviceType {
    name: Cow::Borrowed("Logitech Pro X3 Superstrike"),
    vid: 0x046D, // Logitech
    pid: 0xC54F, // Lightspeed receiver
    filter: Filter { usage_page: Some(0xFF43), usage: Some(0x0302), interface_number: None },
    driver: |_| Box::new(LogitechHidpp),
};

/// Battery of a HID++ 2.0 device with the Unified Battery feature, behind a receiver.
struct LogitechHidpp;

impl LogitechHidpp {
    /// Send a request and return the parameters of its reply, None on error or timeout.
    fn request(device: &dyn HidIo, feature_index: u8, function: u8, params: &[u8]) -> Option<Vec<u8>> {
        let function = (function << 4) | HIDPP_SOFTWARE_ID;
        let mut message = vec![0; HIDPP_REPORT_SIZE];
        message[..4].copy_from_slice(&[HIDPP_LONG_REPORT_ID, HIDPP_RECEIVER_SLOT, feature_index, function]);
        message[4..4 + params.len()].copy_from_slice(params);
        if !device.write(&message) {
            return None;
        }
        let header = [HIDPP_LONG_REPORT_ID, HIDPP_RECEIVER_SLOT, feature_index, function];
        let error = [HIDPP_LONG_REPORT_ID, HIDPP_RECEIVER_SLOT, HIDPP_ERROR, feature_index, function];
        let reply = read_reply(device, HIDPP_REPORT_SIZE, HIDPP_READ_TIMEOUT, |report| {
            report.starts_with(&header) || report.starts_with(&error)
        });
        reply.starts_with(&header).then(|| reply[header.len()..].to_vec())
    }
}

impl Driver for LogitechHidpp {
    fn battery_level(&self, device: &dyn HidIo) -> Option<u8> {
        // The feature index can change with the firmware: ask the device for it
        let feature = Self::request(device, HIDPP_ROOT, HIDPP_GET_FEATURE, &HIDPP_UNIFIED_BATTERY.to_be_bytes());
        let Some(&feature_index) = feature.as_ref().and_then(|params| params.first()).filter(|index| **index != 0)
        else {
            tracing::info!("Logitech HID++ - No battery feature (asleep, off or not paired?)");
            return None;
        };
        // getStatus: state of charge in %, level, charging status, external power
        let status = Self::request(device, feature_index, HIDPP_GET_STATUS, &[])?;
        status.first().copied().filter(|level| *level <= MAX_BATTERY_LEVEL)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::devices::fake::FakeDevice;

    const BATTERY_LEVEL: u8 = 22;
    // Reply to B3 06 as captured from Keychron Ultra-Link 8K firmware 1.06: 22%, on battery
    const BATTERY_REPLY: [u8; 64] = [
        0xB4, 0x06, 0x00, 0x22, 0x22, 0x02, 0x90, 0x01, 0x20, 0x03, 0xE8, 0x03, 0xDC, 0x05, 0xB8, 0x0B, 0x15, 0x05,
        0x04, 0x0A, 0x16, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xB7, 0x00, 0x00, 0x00, 0x04, 0x14, 0x04, 0x04, 0x04,
        0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x05, 0x00, 0x00,
        0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    ];

    fn with_battery(byte: u8) -> Vec<u8> {
        let mut report = BATTERY_REPLY.to_vec();
        report[M6_BATTERY_INDEX] = byte;
        report
    }

    fn notification() -> Vec<u8> {
        [&[0xE2, 0x01, 0x01, 0x00, 0x16][..], &[0; 59]].concat()
    }

    #[test]
    fn parse_battery() {
        let mut other_command = BATTERY_REPLY.to_vec();
        other_command[1] = 0x07;
        for (report, expected) in [
            (BATTERY_REPLY.to_vec(), Some(BATTERY_LEVEL)),
            (with_battery(0xE4), Some(100)), // charging
            (with_battery(0x00), Some(0)),
            (with_battery(0x65), None),
            (BATTERY_REPLY[..20].to_vec(), None), // truncated
            (other_command, None),
            (notification(), None),
            (vec![], None), // timeout
        ] {
            assert_eq!(parse_m6_battery_report(&report), expected, "{report:?}");
        }
    }

    fn battery_level(replies: Vec<Vec<u8>>) -> (Option<u8>, FakeDevice) {
        let receiver = FakeDevice::new(1, [(M6_GET_INFO, replies)]);
        (KeychronM6.battery_level(&receiver), receiver)
    }

    #[test]
    fn reads_battery() {
        let (level, receiver) = battery_level(vec![BATTERY_REPLY.to_vec()]);
        assert_eq!(level, Some(BATTERY_LEVEL));
        let mut expected = vec![0; M6_REPORT_SIZE];
        expected[..2].copy_from_slice(&[0xB3, 0x06]);
        assert_eq!(*receiver.written.borrow(), [expected]);
    }

    #[test]
    fn skips_unrelated_reports() {
        let (level, _) = battery_level(vec![notification(), BATTERY_REPLY.to_vec()]);
        assert_eq!(level, Some(BATTERY_LEVEL));
    }

    #[test]
    fn mouse_asleep() {
        let (level, _) = battery_level(vec![]);
        assert_eq!(level, None);
    }

    // Replies captured from a PRO X3 SUPERSTRIKE on receiver C54F: Unified Battery at index 7, 84%
    const HIDPP_FEATURE_REPLY: [u8; 20] =
        [0x11, 0x01, 0x00, 0x0A, 0x07, 0x00, 0x05, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
    const HIDPP_STATUS_REPLY: [u8; 20] = [0x11, 0x01, 0x07, 0x1A, 0x54, 0x08, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];

    fn hidpp_battery_level(replies: impl IntoIterator<Item = (u8, Vec<Vec<u8>>)>) -> (Option<u8>, FakeDevice) {
        // Keyed by the feature index: 0 for IRoot, 7 for Unified Battery
        let receiver = FakeDevice::new(2, replies);
        (LogitechHidpp.battery_level(&receiver), receiver)
    }

    #[test]
    fn hidpp_reads_battery() {
        let (level, receiver) = hidpp_battery_level([
            (0x00, vec![HIDPP_FEATURE_REPLY.to_vec()]),
            (0x07, vec![HIDPP_STATUS_REPLY.to_vec()]),
        ]);
        assert_eq!(level, Some(84));
        let written = receiver.written.borrow();
        assert_eq!(written[0][..6], [0x11, 0x01, 0x00, 0x0A, 0x10, 0x04]);
        assert_eq!(written[1][..4], [0x11, 0x01, 0x07, 0x1A]);
        assert!(written.iter().all(|message| message.len() == 20));
    }

    #[test]
    fn hidpp_skips_unrelated_reports() {
        let notification = vec![0x11, 0x01, 0x07, 0x00, 0x50, 0x04];
        let (level, _) = hidpp_battery_level([
            (0x00, vec![HIDPP_FEATURE_REPLY.to_vec()]),
            (0x07, vec![notification, HIDPP_STATUS_REPLY.to_vec()]),
        ]);
        assert_eq!(level, Some(84));
    }

    #[test]
    fn hidpp_no_battery() {
        let error = vec![0x11, 0x01, 0xFF, 0x00, 0x0A, 0x05];
        let mut no_feature = HIDPP_FEATURE_REPLY.to_vec();
        no_feature[4] = 0;
        for replies in [vec![], vec![error], vec![no_feature]] {
            let (level, receiver) = hidpp_battery_level([(0x00, replies)]);
            assert_eq!(level, None);
            assert_eq!(receiver.written.borrow().len(), 1);
        }
    }

    #[test]
    fn razer_message() {
        let message = RazerProClickMini::battery_message();
        assert_eq!(message.len(), 91);
        assert_eq!(message[..9], [0, 0, 0x1F, 0, 0, 0, 0x02, 0x07, 0x80]);
        assert_eq!(message[89], 0x85);
    }
}
