//! Sources of battery readings: HID devices with a driver, and devices the OS reports (e.g. Bluetooth).

use std::collections::HashMap;
use std::ffi::CString;
use std::path::PathBuf;
use std::sync::{Mutex, MutexGuard, PoisonError};
use std::thread;

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
/// Device types are read in parallel, see `read_groups`.
#[derive(Default)]
pub struct HidProvider {
    /// Locked only to search and open devices, not while reading them: hidapi keeps the error of a failed open in
    /// a global, which two opens failing at the same time would free twice.
    api: Mutex<Option<HidApi>>,
    devices: HashMap<String, FoundDevice>,
    /// Read on each read, see `extra_devices`. None: only the built-in devices.
    extra_devices_file: Option<PathBuf>,
}

impl HidProvider {
    pub fn new(extra_devices_file: PathBuf) -> Self {
        Self { extra_devices_file: Some(extra_devices_file), ..Self::default() }
    }

    fn lock_api(&self) -> MutexGuard<'_, Option<HidApi>> {
        self.api.lock().unwrap_or_else(PoisonError::into_inner)
    }

    /// Every HID collection matching the device type, each with its own driver. Empty when none is found.
    fn candidates(&self, device_type: &DeviceType) -> Vec<FoundDevice> {
        let mut api = self.lock_api();
        if api.is_none() {
            // Devices are searched one type at a time, see `find`
            HidApi::disable_device_discovery();
            match HidApi::new() {
                Ok(new_api) => *api = Some(new_api),
                Err(e) => tracing::error!("Error initializing hidapi: {e}"),
            }
        }
        let Some(api) = api.as_mut() else { return Vec::new() };
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
        let opened = self.lock_api().as_ref()?.open_path(&device.path);
        let level = match opened {
            Ok(hid_device) => device.driver.battery_level(&hid_device),
            Err(e) => {
                tracing::warn!("Error opening {}: {e}", device_type.name);
                None
            }
        };
        tracing::info!("{} - Battery level: {level:?} / {:?}", device_type.name, device.path);
        level
    }

    /// Read the stored device, returned with the level when it answers. One that does not answer is searched again:
    /// it may have come back under a new path, e.g. after the computer slept, and the stored one would keep failing.
    fn level(&self, device_type: &DeviceType, stored: Option<FoundDevice>) -> (Lookup, Option<FoundDevice>) {
        if let Some(device) = stored {
            if let Some(level) = self.read_level(device_type, &device) {
                return (Lookup::Found(Some(level)), Some(device));
            }
            tracing::info!("No answer from {}, searching it again", device_type.name);
        }
        let candidates = self.candidates(device_type);
        if candidates.is_empty() {
            tracing::info!("Device not found: {}", device_type.name);
        }
        let (lookup, answering) = first_answering(candidates, |device| self.read_level(device_type, device));
        if let Some(device) = &answering {
            tracing::info!("Device found for {}: {:?}", device_type.name, device.path);
        }
        (lookup, answering)
    }
}

impl BatteryProvider for HidProvider {
    fn read(&mut self, settings: &Settings) -> Vec<BatteryReading> {
        let mut stored = std::mem::take(&mut self.devices);
        let device_types = extra_devices::device_types(self.extra_devices_file.as_deref())
            .into_iter()
            .filter(|device_type| settings.is_enabled(&device_type.name))
            .map(|device_type| {
                let device = stored.remove(&*device_type.name);
                (device_type, device)
            });
        // Device types behind the same receiver are read one after the other, their replies could mix otherwise
        let this = &*self;
        let lookups = read_groups(
            device_types,
            |(device_type, _)| (device_type.vid, device_type.pid),
            |(device_type, device)| (this.level(&device_type, device), device_type.name),
        );
        lookups
            .into_iter()
            .filter_map(|((lookup, device), name)| {
                if let Some(device) = device {
                    self.devices.insert(name.to_string(), device);
                }
                match lookup {
                    Lookup::NotFound => None,
                    Lookup::Found(level) => Some(BatteryReading { name: name.into_owned(), level }),
                }
            })
            .collect()
    }
}

/// Run `read` on every item, each in its own thread. The results are in the order of `items`.
pub fn read_parallel<T: Send, R: Send>(items: impl IntoIterator<Item = T>, read: impl Fn(T) -> R + Sync) -> Vec<R> {
    let read = &read;
    thread::scope(|scope| {
        let threads: Vec<_> = items.into_iter().map(|item| scope.spawn(move || read(item))).collect();
        threads.into_iter().map(|thread| thread.join().unwrap_or_else(|e| std::panic::resume_unwind(e))).collect()
    })
}

/// Run `read` on every item: items with the same key one after the other in one thread, in their order, the
/// others in parallel. The results are in the order of `items`.
fn read_groups<T: Send, K: PartialEq, R: Send>(
    items: impl IntoIterator<Item = T>,
    key: impl Fn(&T) -> K,
    read: impl Fn(T) -> R + Sync,
) -> Vec<R> {
    let mut groups: Vec<(K, Vec<(usize, T)>)> = Vec::new();
    for (index, item) in items.into_iter().enumerate() {
        let item_key = key(&item);
        match groups.iter_mut().find(|(group_key, _)| *group_key == item_key) {
            Some((_, group)) => group.push((index, item)),
            None => groups.push((item_key, vec![(index, item)])),
        }
    }
    let groups = groups.into_iter().map(|(_, group)| group);
    let mut results: Vec<_> =
        read_parallel(groups, |group| group.into_iter().map(|(index, item)| (index, read(item))).collect::<Vec<_>>())
            .into_iter()
            .flatten()
            .collect();
    results.sort_by_key(|(index, _)| *index);
    results.into_iter().map(|(_, result)| result).collect()
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
pub(crate) mod tests {
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
        assert!(provider.lock_api().is_none(), "hidapi was initialized");
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

    /// Two ends that each wait for the other: they only both return true when run at the same time. Waiting only
    /// happens when they are not, so the tests stay fast.
    pub fn handshake() -> [Handshake; 2] {
        let (first_sender, first_receiver) = std::sync::mpsc::channel();
        let (second_sender, second_receiver) = std::sync::mpsc::channel();
        [Handshake(first_sender, second_receiver), Handshake(second_sender, first_receiver)]
    }

    pub struct Handshake(std::sync::mpsc::Sender<()>, std::sync::mpsc::Receiver<()>);

    impl Handshake {
        pub fn meet(&self) -> bool {
            let _ = self.0.send(());
            self.1.recv_timeout(std::time::Duration::from_secs(1)).is_ok()
        }
    }

    #[test]
    fn read_groups_reads_groups_in_parallel() {
        let [first, second] = handshake();
        let met = read_groups([(1, first), (2, second)], |(key, _)| *key, |(_, end)| end.meet());
        assert_eq!(met, [true, true]);
    }

    #[test]
    fn read_groups_reads_a_group_in_order_and_keeps_the_order_of_items() {
        let read = std::sync::Mutex::new(Vec::new());
        let threads = read_groups(
            [('a', 0), ('b', 1), ('a', 2), ('a', 3)],
            |(key, _)| *key,
            |(_, index)| {
                read.lock().unwrap().push(index);
                (index, thread::current().id())
            },
        );
        assert_eq!(threads.iter().map(|(index, _)| *index).collect::<Vec<_>>(), [0, 1, 2, 3]);
        assert!(threads[0].1 == threads[2].1 && threads[2].1 == threads[3].1, "group a in one thread");
        assert_ne!(threads[0].1, threads[1].1);
        let group_a: Vec<_> = read.into_inner().unwrap().into_iter().filter(|index| *index != 1).collect();
        assert_eq!(group_a, [0, 2, 3]);
    }

    #[test]
    fn display_reading() {
        assert_eq!(BatteryReading { name: "Mouse".to_string(), level: Some(42) }.to_string(), "Mouse: 42%");
        assert_eq!(BatteryReading { name: "Mouse".to_string(), level: None }.to_string(), "Mouse: N/A");
    }
}
