use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};

use crate::core::paths::seen_devices_file;
use crate::core::providers::{BatteryProvider, BatteryReading, HidProvider};
use crate::core::settings::Settings;

pub struct Poller {
    providers: Vec<Box<dyn BatteryProvider>>,
    seen_devices_file: PathBuf,
}

impl Poller {
    pub fn new(providers: Vec<Box<dyn BatteryProvider>>) -> Self {
        Self::with_seen_devices_file(providers, seen_devices_file())
    }

    pub fn with_seen_devices_file(providers: Vec<Box<dyn BatteryProvider>>, seen_devices_file: PathBuf) -> Self {
        Self { providers, seen_devices_file }
    }

    pub fn poll(&mut self, settings: &Settings) -> Vec<BatteryReading> {
        let readings: Vec<_> = self.providers.iter_mut().flat_map(|provider| provider.read(settings)).collect();
        remember_devices(&self.seen_devices_file, readings.iter().map(|reading| reading.name.clone()).collect());
        readings
    }
}

pub fn load_seen_devices(path: &Path) -> BTreeSet<String> {
    fs::read_to_string(path).ok().and_then(|text| serde_json::from_str(&text).ok()).unwrap_or_default()
}

/// Keep the name of every device ever seen, so the settings dialog can list them while disconnected.
fn remember_devices(path: &Path, names: BTreeSet<String>) {
    let mut seen = load_seen_devices(path);
    if names.is_subset(&seen) {
        return;
    }
    seen.extend(names);
    let written = serde_json::to_string(&seen).map_err(std::io::Error::other).and_then(|text| fs::write(path, text));
    if let Err(e) = written {
        tracing::warn!("Could not save seen devices: {e}");
    }
}

pub fn known_device_names(settings: &Settings, seen_devices_file: &Path) -> Vec<String> {
    let mut names = load_seen_devices(seen_devices_file);
    names.extend(HidProvider::device_names().into_iter().map(String::from));
    names.extend(settings.disabled_devices.iter().cloned());
    names.into_iter().collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    struct FakeProvider(Vec<BatteryReading>);

    impl BatteryProvider for FakeProvider {
        fn read(&mut self, _settings: &Settings) -> Vec<BatteryReading> {
            self.0.clone()
        }
    }

    fn reading(name: &str, level: Option<u8>) -> BatteryReading {
        BatteryReading { name: name.to_string(), level }
    }

    fn names(names: &[&str]) -> BTreeSet<String> {
        names.iter().map(ToString::to_string).collect()
    }

    fn poll(path: &Path, readings: Vec<BatteryReading>) -> Vec<BatteryReading> {
        let provider: Box<dyn BatteryProvider> = Box::new(FakeProvider(readings));
        Poller::with_seen_devices_file(vec![provider], path.to_path_buf()).poll(&Settings::default())
    }

    #[test]
    fn poll_merges_providers_and_remembers_devices() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("seen_devices.json");
        let (mouse, headset) = (reading("Mouse", Some(50)), reading("Headset", None));
        let providers: Vec<Box<dyn BatteryProvider>> =
            vec![Box::new(FakeProvider(vec![mouse.clone()])), Box::new(FakeProvider(vec![headset.clone()]))];

        let readings = Poller::with_seen_devices_file(providers, path.clone()).poll(&Settings::default());

        assert_eq!(readings, [mouse, headset]);
        assert_eq!(load_seen_devices(&path), names(&["Mouse", "Headset"]));
    }

    #[test]
    fn seen_devices_are_kept_while_disconnected() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("seen_devices.json");
        poll(&path, vec![reading("Mouse", Some(50))]);
        poll(&path, vec![reading("Headset", Some(80))]);
        assert_eq!(load_seen_devices(&path), names(&["Mouse", "Headset"]));
    }

    #[test]
    fn known_device_names_are_sorted_and_merged() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("seen_devices.json");
        fs::write(&path, r#"["Earbuds"]"#).unwrap();
        let settings = Settings { disabled_devices: names(&["Old speaker"]), ..Settings::default() };

        let known = known_device_names(&settings, &path);

        let mut expected = names(&["Earbuds", "Old speaker"]);
        expected.extend(HidProvider::device_names().into_iter().map(String::from));
        assert_eq!(known, expected.into_iter().collect::<Vec<_>>());
    }

    #[test]
    fn corrupted_seen_devices_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("seen_devices.json");
        fs::write(&path, "{").unwrap();
        assert!(load_seen_devices(&path).is_empty());
    }
}
