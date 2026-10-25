//! HID devices with a driver to read their battery level.

pub mod dualsense;
pub mod headset;
pub mod keyboard;
pub mod mouse;

use std::time::{Duration, Instant};

use hidapi::HidDevice;

/// Raw HID access, implemented by `hidapi::HidDevice` and by fakes in tests.
pub trait HidIo {
    fn write(&self, data: &[u8]) -> bool;
    /// Up to `size` bytes, empty on timeout or error.
    fn read(&self, size: usize, timeout_ms: i32) -> Vec<u8>;
    fn send_feature_report(&self, data: &[u8]) -> bool;
    /// The report with its ID as first byte, empty on error.
    fn get_feature_report(&self, report_id: u8, size: usize) -> Vec<u8>;
}

impl HidIo for HidDevice {
    fn write(&self, data: &[u8]) -> bool {
        HidDevice::write(self, data).inspect_err(|e| tracing::error!("Error hid_write: {e} / {data:?}")).is_ok()
    }

    fn read(&self, size: usize, timeout_ms: i32) -> Vec<u8> {
        let mut buffer = vec![0; size];
        match self.read_timeout(&mut buffer, timeout_ms) {
            Ok(read) => buffer.truncate(read),
            Err(e) => {
                tracing::error!("Error hid_read: {e} / size = {size} / timeout_ms = {timeout_ms}");
                buffer.clear();
            }
        }
        buffer
    }

    fn send_feature_report(&self, data: &[u8]) -> bool {
        HidDevice::send_feature_report(self, data)
            .inspect_err(|e| tracing::error!("Error send_feature_report: {e} / {data:?}"))
            .is_ok()
    }

    fn get_feature_report(&self, report_id: u8, size: usize) -> Vec<u8> {
        let mut buffer = vec![0; size];
        buffer[0] = report_id;
        match HidDevice::get_feature_report(self, &mut buffer) {
            Ok(read) => buffer.truncate(read),
            Err(e) => {
                tracing::error!("Error get_feature_report: {e} / report_id = {report_id} / size = {size}");
                buffer.clear();
            }
        }
        buffer
    }
}

/// Reads the battery level of an opened device, None when it does not answer.
pub trait Driver: Send {
    fn battery_level(&self, device: &dyn HidIo) -> Option<u8>;
}

/// Which HID interface of the device to talk to: None matches any value.
#[derive(Clone, Copy, Debug, Default)]
pub struct Filter {
    pub usage_page: Option<u16>,
    pub usage: Option<u16>,
    pub interface_number: Option<i32>,
}

impl Filter {
    pub const ANY: Self = Self { usage_page: None, usage: None, interface_number: None };

    pub fn matches(&self, usage_page: u16, usage: u16, interface_number: i32) -> bool {
        self.usage_page.is_none_or(|expected| expected == usage_page)
            && self.usage.is_none_or(|expected| expected == usage)
            && self.interface_number.is_none_or(|expected| expected == interface_number)
    }
}

pub struct DeviceType {
    pub name: &'static str,
    pub vid: u16,
    pub pid: u16,
    pub filter: Filter,
    /// Create the driver, given whether the device is connected over USB.
    pub driver: fn(bool) -> Box<dyn Driver>,
}

pub const HID_DEVICES: [DeviceType; 5] = [
    mouse::RAZER_PRO_CLICK_MINI,
    headset::HYPERX_CLOUD_ALPHA_WIRELESS,
    dualsense::DUALSENSE,
    keyboard::KEYCHRON_K2_HE,
    mouse::KEYCHRON_M6,
];

/// Read reports until one is accepted by `is_reply`, skipping unrelated ones. Empty on timeout.
pub fn read_reply(device: &dyn HidIo, size: usize, timeout: Duration, is_reply: impl Fn(&[u8]) -> bool) -> Vec<u8> {
    let deadline = Instant::now() + timeout;
    loop {
        let remaining = deadline.saturating_duration_since(Instant::now());
        let remaining_ms = i32::try_from(remaining.as_millis()).unwrap_or(i32::MAX);
        if remaining_ms <= 0 {
            return Vec::new();
        }
        let report = device.read(size, remaining_ms);
        if report.is_empty() || is_reply(&report) {
            return report;
        }
    }
}

#[cfg(test)]
pub mod fake {
    use std::cell::RefCell;
    use std::collections::{HashMap, VecDeque};

    use super::HidIo;

    /// Replies to each written message with the reports given for the message's command byte, in order.
    pub struct FakeDevice {
        command_index: usize,
        replies: HashMap<u8, Vec<Vec<u8>>>,
        pending: RefCell<VecDeque<Vec<u8>>>,
        pub written: RefCell<Vec<Vec<u8>>>,
    }

    impl FakeDevice {
        pub fn new(command_index: usize, replies: impl IntoIterator<Item = (u8, Vec<Vec<u8>>)>) -> Self {
            Self {
                command_index,
                replies: replies.into_iter().collect(),
                pending: RefCell::default(),
                written: RefCell::default(),
            }
        }
    }

    impl HidIo for FakeDevice {
        fn write(&self, data: &[u8]) -> bool {
            self.written.borrow_mut().push(data.to_vec());
            *self.pending.borrow_mut() =
                self.replies.get(&data[self.command_index]).cloned().unwrap_or_default().into();
            true
        }

        fn read(&self, size: usize, _timeout_ms: i32) -> Vec<u8> {
            let mut report = self.pending.borrow_mut().pop_front().unwrap_or_default();
            report.truncate(size);
            report
        }

        fn send_feature_report(&self, _data: &[u8]) -> bool {
            true
        }

        fn get_feature_report(&self, _report_id: u8, _size: usize) -> Vec<u8> {
            Vec::new()
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn filter_matches_only_given_values() {
        let raw_hid = Filter { usage_page: Some(0xFF60), usage: Some(0x61), ..Filter::ANY };
        assert!(raw_hid.matches(0xFF60, 0x61, 2));
        assert!(!raw_hid.matches(0x01, 0x06, 1));
        assert!(Filter::ANY.matches(0x01, 0x06, 1));
        assert!(!Filter { interface_number: Some(0), ..Filter::ANY }.matches(0x01, 0x02, 1));
    }

    #[test]
    fn device_names_are_unique() {
        let mut names: Vec<_> = HID_DEVICES.iter().map(|device_type| device_type.name).collect();
        names.sort_unstable();
        names.dedup();
        assert_eq!(names.len(), HID_DEVICES.len());
    }
}
