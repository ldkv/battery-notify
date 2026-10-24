use std::collections::HashMap;
use std::time::{Duration, Instant};

use crate::core::providers::BatteryReading;
use crate::core::settings::Settings;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum BatteryStatus {
    Normal,
    Low,
    Critical,
}

pub fn lowest_level(readings: &[BatteryReading]) -> Option<u8> {
    readings.iter().filter_map(|reading| reading.level).min()
}

pub fn battery_status(level: Option<u8>, settings: &Settings) -> BatteryStatus {
    match level.map(i64::from) {
        None => BatteryStatus::Normal,
        Some(level) if level > settings.low_threshold => BatteryStatus::Normal,
        Some(level) if level > settings.critical_threshold => BatteryStatus::Low,
        Some(_) => BatteryStatus::Critical,
    }
}

/// Decide which devices to notify about: when a device drops to the low level,
/// then again every `renotify_minutes` while it stays low.
#[derive(Default)]
pub struct Notifier {
    notified_at: HashMap<String, Instant>,
}

impl Notifier {
    pub fn due(&mut self, readings: &[BatteryReading], settings: &Settings, now: Instant) -> Vec<BatteryReading> {
        let renotify = Duration::from_secs(u64::try_from(settings.renotify_minutes).unwrap_or(0) * 60);
        let mut due = Vec::new();
        for reading in readings {
            if reading.level.is_none() {
                continue; // did not answer this time: keep its state
            }
            if battery_status(reading.level, settings) == BatteryStatus::Normal {
                self.notified_at.remove(&reading.name);
                continue;
            }
            if let Some(notified_at) = self.notified_at.get(&reading.name)
                && (renotify.is_zero() || now.duration_since(*notified_at) < renotify)
            {
                continue;
            }
            self.notified_at.insert(reading.name.clone(), now);
            due.push(reading.clone());
        }
        due
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const HOUR: Duration = Duration::from_hours(1);

    fn settings() -> Settings {
        Settings { low_threshold: 20, critical_threshold: 10, renotify_minutes: 60, ..Settings::default() }
    }

    fn reading(name: &str, level: Option<u8>) -> BatteryReading {
        BatteryReading { name: name.to_string(), level }
    }

    #[test]
    fn lowest_level_ignores_devices_without_level() {
        let readings = [reading("Mouse", Some(50)), reading("Headset", None), reading("Pad", Some(30))];
        assert_eq!(lowest_level(&readings), Some(30));
        assert_eq!(lowest_level(&[reading("Headset", None)]), None);
    }

    #[test]
    fn statuses() {
        for (level, status) in [
            (None, BatteryStatus::Normal),
            (Some(100), BatteryStatus::Normal),
            (Some(21), BatteryStatus::Normal),
            (Some(20), BatteryStatus::Low),
            (Some(11), BatteryStatus::Low),
            (Some(10), BatteryStatus::Critical),
            (Some(0), BatteryStatus::Critical),
        ] {
            assert_eq!(battery_status(level, &settings()), status, "{level:?}");
        }
    }

    #[test]
    fn notify_once_then_every_renotify_interval() {
        let (mut notifier, start) = (Notifier::default(), Instant::now());
        let low = [reading("Mouse", Some(15))];

        assert_eq!(notifier.due(&low, &settings(), start), low);
        assert_eq!(notifier.due(&low, &settings(), start + Duration::from_secs(HOUR.as_secs() - 1)), []);
        assert_eq!(notifier.due(&low, &settings(), start + HOUR), low);
    }

    #[test]
    fn renotify_disabled() {
        let (mut notifier, start) = (Notifier::default(), Instant::now());
        let low = [reading("Mouse", Some(15))];
        let settings = Settings { renotify_minutes: 0, ..Settings::default() };

        assert_eq!(notifier.due(&low, &settings, start), low);
        assert_eq!(notifier.due(&low, &settings, start + 10 * HOUR), []);
    }

    #[test]
    fn notify_again_after_recharging() {
        let (mut notifier, now) = (Notifier::default(), Instant::now());
        let (low, charged) = ([reading("Mouse", Some(15))], [reading("Mouse", Some(80))]);

        assert_eq!(notifier.due(&low, &settings(), now), low);
        assert_eq!(notifier.due(&charged, &settings(), now), []);
        assert_eq!(notifier.due(&low, &settings(), now), low);
    }

    #[test]
    fn each_device_is_notified_on_its_own() {
        let (mut notifier, now) = (Notifier::default(), Instant::now());
        let (mouse, headset) = (reading("Mouse", Some(15)), reading("Headset", Some(5)));

        assert_eq!(notifier.due(std::slice::from_ref(&mouse), &settings(), now), std::slice::from_ref(&mouse));
        assert_eq!(notifier.due(&[mouse, headset.clone()], &settings(), now), [headset]);
    }

    #[test]
    fn device_not_answering_keeps_its_state() {
        let (mut notifier, now) = (Notifier::default(), Instant::now());
        let (low, unknown) = ([reading("Mouse", Some(15))], [reading("Mouse", None)]);

        assert_eq!(notifier.due(&low, &settings(), now), low);
        assert_eq!(notifier.due(&unknown, &settings(), now), []);
        assert_eq!(notifier.due(&low, &settings(), now), []);
    }
}
