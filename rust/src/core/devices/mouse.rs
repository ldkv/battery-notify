use std::thread;
use std::time::Duration;

use super::{DeviceType, Driver, Filter, HidIo, read_reply};

pub const RAZER_PRO_CLICK_MINI: DeviceType = DeviceType {
    name: "Razer Pro Click Mini",
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
    name: "Keychron M6",
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

    #[test]
    fn razer_message() {
        let message = RazerProClickMini::battery_message();
        assert_eq!(message.len(), 91);
        assert_eq!(message[..9], [0, 0, 0x1F, 0, 0, 0, 0x02, 0x07, 0x80]);
        assert_eq!(message[89], 0x85);
    }
}
