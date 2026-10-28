//! Sources of battery readings: HID devices with a driver, and devices the OS reports (e.g. Bluetooth).

use std::collections::HashMap;
use std::ffi::CString;

use hidapi::{BusType, HidApi};

use crate::core::devices::{DeviceType, Driver, HID_DEVICES};
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
    devices: HashMap<&'static str, FoundDevice>,
}

impl HidProvider {
    pub fn device_names() -> Vec<&'static str> {
        HID_DEVICES.iter().map(|device_type| device_type.name).collect()
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

    fn find(&mut self, device_type: &DeviceType) -> Option<&FoundDevice> {
        if !self.devices.contains_key(device_type.name) {
            let api = self.api()?;
            let searched = api.reset_devices().and_then(|()| api.add_devices(device_type.vid, device_type.pid));
            if let Err(e) = searched {
                tracing::info!("Error searching {}: {e}", device_type.name);
                return None;
            }
            let Some((path, is_usb)) = api
                .device_list()
                .find(|info| device_type.filter.matches(info.usage_page(), info.usage(), info.interface_number()))
                .map(|info| (info.path().to_owned(), matches!(info.bus_type(), BusType::Usb)))
            else {
                tracing::info!("Device not found: {}", device_type.name);
                return None;
            };
            tracing::info!("Device found for {}: {path:?}", device_type.name);
            self.devices.insert(device_type.name, FoundDevice { path, driver: (device_type.driver)(is_usb) });
        }
        self.devices.get(device_type.name)
    }

    /// None when the device is not found.
    fn reading(&mut self, device_type: &DeviceType) -> Option<BatteryReading> {
        let lookup = read_searching_again(
            self,
            |provider| provider.level(device_type),
            |provider| {
                tracing::info!("No answer from {}, searching it again", device_type.name);
                provider.devices.remove(device_type.name);
            },
        );
        match lookup {
            Lookup::NotFound => None,
            Lookup::Found(level) => Some(BatteryReading { name: device_type.name.to_string(), level }),
        }
    }

    fn level(&mut self, device_type: &DeviceType) -> Lookup {
        if self.find(device_type).is_none() {
            return Lookup::NotFound;
        }
        let Some(api) = self.api.as_ref() else { return Lookup::NotFound };
        let device = &self.devices[device_type.name];
        let level = match api.open_path(&device.path) {
            Ok(hid_device) => device.driver.battery_level(&hid_device),
            Err(e) => {
                tracing::warn!("Error opening {}: {e}", device_type.name);
                None
            }
        };
        tracing::info!("{} - Battery level: {level:?}", device_type.name);
        Lookup::Found(level)
    }
}

impl BatteryProvider for HidProvider {
    fn read(&mut self, settings: &Settings) -> Vec<BatteryReading> {
        HID_DEVICES
            .iter()
            .filter(|device_type| settings.is_enabled(device_type.name))
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

/// Read with `read`. A device that does not answer is forgotten and searched again: it may have come
/// back under a new path, e.g. after the computer slept, and the stored one would keep failing.
fn read_searching_again<S>(state: &mut S, read: impl Fn(&mut S) -> Lookup, forget: impl Fn(&mut S)) -> Lookup {
    match read(state) {
        Lookup::Found(None) => {
            forget(state);
            read(state)
        }
        lookup => lookup,
    }
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
        let disabled = HidProvider::device_names().into_iter().map(String::from).collect();
        assert_eq!(provider.read(&Settings { disabled_devices: disabled, ..Settings::default() }), []);
        assert!(provider.api.is_none(), "hidapi was initialized");
    }

    /// A device found under a stored path that answers in turn `answers`, until forgotten and searched again.
    struct Searches {
        found: Vec<Vec<Option<u8>>>, // what each search finds, in turn: None when not found
        current: Option<std::vec::IntoIter<Option<u8>>>,
    }

    impl Searches {
        fn new(found: Vec<Option<Vec<Option<u8>>>>) -> Self {
            Self { found: found.into_iter().map(Option::unwrap_or_default).rev().collect(), current: None }
        }

        fn read(&mut self) -> Lookup {
            if self.current.is_none() {
                match self.found.pop() {
                    Some(answers) if !answers.is_empty() => self.current = Some(answers.into_iter()),
                    _ => return Lookup::NotFound,
                }
            }
            Lookup::Found(self.current.as_mut().and_then(Iterator::next).flatten())
        }

        fn forget(&mut self) {
            self.current = None;
        }
    }

    fn read(searches: &mut Searches) -> Lookup {
        read_searching_again(searches, Searches::read, Searches::forget)
    }

    #[test]
    fn device_that_stops_answering_is_searched_again() {
        // After the computer slept, the device comes back under a new path: the stored one fails
        let mut searches = Searches::new(vec![Some(vec![Some(80), None]), Some(vec![Some(42)])]);
        assert_eq!(read(&mut searches), Lookup::Found(Some(80)));
        assert_eq!(read(&mut searches), Lookup::Found(Some(42)));
    }

    #[test]
    fn device_no_longer_found_is_dropped() {
        let mut searches = Searches::new(vec![Some(vec![Some(80), None]), None]);
        assert_eq!(read(&mut searches), Lookup::Found(Some(80)));
        assert_eq!(read(&mut searches), Lookup::NotFound);
    }

    #[test]
    fn found_device_that_does_not_answer_has_no_level() {
        // E.g. a receiver whose keyboard is asleep: found again, still without a level
        let mut searches = Searches::new(vec![Some(vec![None]), Some(vec![None])]);
        assert_eq!(read(&mut searches), Lookup::Found(None));
    }

    #[test]
    fn display_reading() {
        assert_eq!(BatteryReading { name: "Mouse".to_string(), level: Some(42) }.to_string(), "Mouse: 42%");
        assert_eq!(BatteryReading { name: "Mouse".to_string(), level: None }.to_string(), "Mouse: N/A");
    }
}
