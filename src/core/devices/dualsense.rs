//! DualSense controller via USB or Bluetooth.
//! Docs: <https://controllers.fandom.com/wiki/Sony_DualSense>
//! Inspired by: <https://github.com/nondebug/dualsense>

use std::thread;
use std::time::Duration;

use super::{DeviceType, Driver, Filter, HidIo};

const BLUETOOTH_BATTERY_INDEX: usize = 54;
const USB_BATTERY_INDEX: usize = 53;
const FEATURE_REPORT_ID: u8 = 0x05;
const FEATURE_REPORT_SIZE: usize = 78;
const READ_TIMEOUT_MS: i32 = 1000;

pub const DUALSENSE: DeviceType = DeviceType {
    name: "DualSense controller",
    vid: 0x054C, // Sony
    pid: 0x0CE6, // DualSense
    filter: Filter { usage: Some(5), ..Filter::ANY },
    driver: |is_usb| Box::new(DualSense { is_bluetooth: !is_usb }),
};

struct DualSense {
    is_bluetooth: bool,
}

/// Battery level is a number from 0 to 10 in the low 4 bits, the charging state in the high 4 bits.
pub fn convert_battery_byte(battery_byte: u8) -> u8 {
    (battery_byte & 0x0F) * 10
}

impl Driver for DualSense {
    /// By default, a Bluetooth-connected DualSense only sends input report 0x01 which omits battery data.
    /// Reading feature report 0x05 activates sending input report 0x31 which includes battery data.
    fn battery_level(&self, device: &dyn HidIo) -> Option<u8> {
        let battery_index = if self.is_bluetooth {
            device.get_feature_report(FEATURE_REPORT_ID, FEATURE_REPORT_SIZE);
            thread::sleep(Duration::from_millis(100));
            BLUETOOTH_BATTERY_INDEX
        } else {
            USB_BATTERY_INDEX
        };
        let response = device.read(battery_index + 1, READ_TIMEOUT_MS);
        response.get(battery_index).copied().map(convert_battery_byte)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn battery_byte() {
        assert_eq!(convert_battery_byte(0x00), 0);
        assert_eq!(convert_battery_byte(0x15), 50); // charging, 5
        assert_eq!(convert_battery_byte(0x2A), 100); // complete, 10
    }
}
