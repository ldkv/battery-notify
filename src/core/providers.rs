//! Sources of battery readings: HID devices with a driver, and devices the OS reports (e.g. Bluetooth).

use std::collections::HashMap;
use std::ffi::CString;
use std::path::PathBuf;

use hidapi::{BusType, HidApi};

use crate::core::devices::{DeviceType, Driver};
use crate::core::extra_devices;
use crate::core::settings::Settings;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BatteryReading {
    pub name: String,
    pub level: Option<u8>, // None when the device did not answer
}

impl std::fmt::Display for BatteryReading {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self.level {
            Some(level) => write!(f, "{}: {level}%", self.name),
            None => write!(f, "{}: N/A", self.name),
        }
    }
}

pub trait BatteryProvider: Send {
    fn read(&mut self, settings: &Settings) -> Vec<BatteryReading>;
}

struct FoundDevice {
    path: CString,
    driver: Box<dyn Driver>,
}

/// Devices are looked up once found, and searched again on each read until then, or when they stop answering.
#[derive(Default)]
pub struct HidProvider {
    api: Option<HidApi>,
    devices: HashMap<String, FoundDevice>,
    /// Read on each read, see `extra_devices`. None: only the built-in devices.
    extra_devices_file: Option<PathBuf>,
}

impl HidProvider {
    pub fn new(extra_devices_file: PathBuf) -> Self {
        Self { extra_devices_file: Some(extra_devices_file), ..Self::default() }
    }

    fn api(&mut self) -> Option<&mut HidApi> {
        if self.api.is_none() {
            // Devices are searched one type at a time, see `find`
            HidApi::disable_device_discovery();
            match HidApi::new() {
                Ok(api) => self.api = Some(api),
                Err(e) => tracing::error!("Error initializing hidapi: {e}"),
            }
        }
        self.api.as_mut()
    }

    /// Every HID collection matching the device type, each with its own driver. Empty when none is found.
    fn candidates(&mut self, device_type: &DeviceType) -> Vec<FoundDevice> {
        let Some(api) = self.api() else { return Vec::new() };
        let searched = api.reset_devices().and_then(|()| api.add_devices(device_type.vid, device_type.pid));
        if let Err(e) = searched {
            tracing::info!("Error searching {}: {e}", device_type.name);
            return Vec::new();
        }
        api.device_list()
            .filter(|info| device_type.filter.matches(info.usage_page(), info.usage(), info.interface_number()))
            .map(|info| FoundDevice {
                path: info.path().to_owned(),
                driver: (device_type.driver)(matches!(info.bus_type(), BusType::Usb)),
            })
            .collect()
    }

    /// Open the device and read its level, None when it does not answer.
    fn read_level(&self, device_type: &DeviceType, device: &FoundDevice) -> Option<u8> {
        let api = self.api.as_ref()?;
        let level = match api.open_path(&device.path) {
            Ok(hid_device) => device.driver.battery_level(&hid_device),
            Err(e) => {
                tracing::warn!("Error opening {}: {e}", device_type.name);
                None
            }
        };
        tracing::info!("{} - Battery level: {level:?} / {:?}", device_type.name, device.path);
        level
    }

    /// None when the device is not found.
    fn reading(&mut self, device_type: &DeviceType) -> Option<BatteryReading> {
        match self.level(device_type) {
            Lookup::NotFound => None,
            Lookup::Found(level) => Some(BatteryReading { name: device_type.name.to_string(), level }),
        }
    }

    /// Read the stored device. One that does not answer is forgotten and searched again: it may have come back
    /// under a new path, e.g. after the computer slept, and the stored one would keep failing.
    fn level(&mut self, device_type: &DeviceType) -> Lookup {
        if let Some(device) = self.devices.get(&*device_type.name) {
            if let Some(level) = self.read_level(device_type, device) {
                return Lookup::Found(Some(level));
            }
            tracing::info!("No answer from {}, searching it again", device_type.name);
            self.devices.remove(&*device_type.name);
        }
        let candidates = self.candidates(device_type);
        if candidates.is_empty() {
            tracing::info!("Device not found: {}", device_type.name);
        }
        let (lookup, answering) = first_answering(candidates, |device| self.read_level(device_type, device));
        if let Some(device) = answering {
            tracing::info!("Device found for {}: {:?}", device_type.name, device.path);
            self.devices.insert(device_type.name.to_string(), device);
        }
        lookup
    }
}

impl BatteryProvider for HidProvider {
    fn read(&mut self, settings: &Settings) -> Vec<BatteryReading> {
        extra_devices::device_types(self.extra_devices_file.as_deref())
            .iter()
            .filter(|device_type| settings.is_enabled(&device_type.name))
            .filter_map(|device_type| self.reading(device_type))
            .collect()
    }
}

#[derive(Debug, PartialEq, Eq)]
enum Lookup {
    NotFound,
    /// The level is None when the device did not answer.
    Found(Option<u8>),
}

/// Read each candidate in turn and return the first that answers, with its level. Several HID collections can
/// match a device type, e.g. two receivers with the same VID/PID, only one of them paired with the device.
fn first_answering<C>(candidates: Vec<C>, read: impl Fn(&C) -> Option<u8>) -> (Lookup, Option<C>) {
    if candidates.is_empty() {
        return (Lookup::NotFound, None);
    }
    for candidate in candidates {
        if let Some(level) = read(&candidate) {
            return (Lookup::Found(Some(level)), Some(candidate));
        }
    }
    (Lookup::Found(None), None)
}

/// Devices whose battery level the OS already knows, e.g. paired Bluetooth devices.
pub struct OsProvider {
    read_batteries: Box<dyn Fn() -> Vec<(String, u8)> + Send>,
}

impl OsProvider {
    pub fn new(read_batteries: impl Fn() -> Vec<(String, u8)> + Send + 'static) -> Self {
        Self { read_batteries: Box::new(read_batteries) }
    }
}

impl BatteryProvider for OsProvider {
    fn read(&mut self, settings: &Settings) -> Vec<BatteryReading> {
        (self.read_batteries)()
            .into_iter()
            .filter(|(name, _)| settings.is_enabled(name))
            .map(|(name, level)| BatteryReading { name, level: Some(level) })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn os_provider_skips_disabled_devices() {
        let mut provider = OsProvider::new(|| vec![("Earbuds".to_string(), 70), ("Keyboard".to_string(), 40)]);
        let settings = Settings { disabled_devices: ["Keyboard".to_string()].into(), ..Settings::default() };
        assert_eq!(provider.read(&settings), [BatteryReading { name: "Earbuds".to_string(), level: Some(70) }]);
    }

    #[test]
    fn hid_provider_does_not_open_disabled_devices() {
        let mut provider = HidProvider::default();
        let disabled =
            extra_devices::device_types(None).into_iter().map(|device_type| device_type.name.into_owned()).collect();
        assert_eq!(provider.read(&Settings { disabled_devices: disabled, ..Settings::default() }), []);
        assert!(provider.api.is_none(), "hidapi was initialized");
    }

    #[test]
    fn first_answering_keeps_the_first_collection_that_answers() {
        // Candidates are indexes into `levels`; returns the lookup, the kept candidate and the ones read
        let first_answering_of = |levels: &[Option<u8>]| {
            let read = std::cell::RefCell::new(Vec::new());
            let (lookup, answering) = first_answering((0..levels.len()).collect(), |index| {
                read.borrow_mut().push(*index);
                levels[*index]
            });
            (lookup, answering, read.into_inner())
        };
        // E.g. two receivers with the same VID/PID, the device paired with the second one
        assert_eq!(first_answering_of(&[None, Some(80), Some(42)]), (Lookup::Found(Some(80)), Some(1), vec![0, 1]));
        // E.g. the device is asleep: nothing is kept, the next read searches again
        assert_eq!(first_answering_of(&[None, None]), (Lookup::Found(None), None, vec![0, 1]));
        assert_eq!(first_answering_of(&[]), (Lookup::NotFound, None, vec![]));
    }

    #[test]
    fn display_reading() {
        assert_eq!(BatteryReading { name: "Mouse".to_string(), level: Some(42) }.to_string(), "Mouse: 42%");
        assert_eq!(BatteryReading { name: "Mouse".to_string(), level: None }.to_string(), "Mouse: N/A");
    }
}
