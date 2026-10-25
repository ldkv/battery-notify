use super::{DeviceType, Driver, Filter, HidIo};

const MESSAGE_SIZE: usize = 52;
const REPORT_ID: u8 = 0x21;
const BATTERY_INDEX: usize = 3;
const READ_TIMEOUT_MS: i32 = 1000;

pub const HYPERX_CLOUD_ALPHA_WIRELESS: DeviceType = DeviceType {
    name: "HyperX Cloud Alpha Wireless",
    vid: 0x03F0,
    pid: 0x098D,
    filter: Filter { usage: Some(514), ..Filter::ANY },
    driver: |_| Box::new(HyperXCloudAlphaWireless),
};

struct HyperXCloudAlphaWireless;

impl Driver for HyperXCloudAlphaWireless {
    fn battery_level(&self, device: &dyn HidIo) -> Option<u8> {
        let mut message = vec![0; MESSAGE_SIZE];
        message[..3].copy_from_slice(&[REPORT_ID, 0xBB, 0x0B]);
        if !device.write(&message) {
            return None;
        }
        device.read(BATTERY_INDEX + 1, READ_TIMEOUT_MS).get(BATTERY_INDEX).copied()
    }
}
