//! User settings, stored as TOML in the same file as the Python version.
//! `FIELDS` describes each setting with its label and limits: the settings dialog is generated from it.

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::io;
use std::path::Path;

use serde::Serialize;
use toml::Value;

use crate::core::paths::config_file;

pub const THRESHOLD_ERROR: &str = "Must be below the low battery level";

pub fn range_error(min: i64, max: i64) -> String {
    format!("Must be between {min} and {max}")
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FieldKind {
    Number { min: i64, max: i64 },
    Checklist,
}

#[derive(Clone, Copy, Debug)]
pub struct Field {
    pub name: &'static str,
    pub label: &'static str,
    pub help: &'static str,
    pub kind: FieldKind,
}

pub const FIELDS: [Field; 5] = [
    Field {
        name: "check_interval_minutes",
        label: "Check interval (minutes)",
        help: "",
        kind: FieldKind::Number { min: 1, max: 120 },
    },
    Field {
        name: "low_threshold",
        label: "Low battery (%)",
        help: "Notify when a device drops to this level",
        kind: FieldKind::Number { min: 1, max: 99 },
    },
    Field {
        name: "critical_threshold",
        label: "Critical battery (%)",
        help: "",
        kind: FieldKind::Number { min: 1, max: 99 },
    },
    Field {
        name: "renotify_minutes",
        label: "Repeat notification (minutes)",
        help: "0 to notify only once",
        kind: FieldKind::Number { min: 0, max: 720 },
    },
    Field {
        name: "disabled_devices",
        label: "Devices",
        help: "Unchecked devices are ignored",
        kind: FieldKind::Checklist,
    },
];

/// Error message per invalid field name.
pub type Errors = BTreeMap<&'static str, String>;

#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Settings {
    pub check_interval_minutes: i64,
    pub low_threshold: i64,
    pub critical_threshold: i64,
    pub renotify_minutes: i64,
    pub disabled_devices: BTreeSet<String>,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            check_interval_minutes: 10,
            low_threshold: 20,
            critical_threshold: 10,
            renotify_minutes: 60,
            disabled_devices: BTreeSet::new(),
        }
    }
}

impl Settings {
    /// Value of a `FieldKind::Number` field.
    pub fn number(&self, name: &str) -> Option<i64> {
        match name {
            "check_interval_minutes" => Some(self.check_interval_minutes),
            "low_threshold" => Some(self.low_threshold),
            "critical_threshold" => Some(self.critical_threshold),
            "renotify_minutes" => Some(self.renotify_minutes),
            _ => None,
        }
    }

    pub fn set_number(&mut self, name: &str, value: i64) {
        match name {
            "check_interval_minutes" => self.check_interval_minutes = value,
            "low_threshold" => self.low_threshold = value,
            "critical_threshold" => self.critical_threshold = value,
            "renotify_minutes" => self.renotify_minutes = value,
            _ => panic!("Not a number setting: {name}"),
        }
    }

    /// Reset one field to its default.
    fn reset(&mut self, name: &str) {
        let defaults = Self::default();
        match defaults.number(name) {
            Some(value) => self.set_number(name, value),
            None => self.disabled_devices = defaults.disabled_devices,
        }
    }

    pub fn validate(&self) -> Errors {
        let mut errors = Errors::new();
        for field in FIELDS {
            if let (FieldKind::Number { min, max }, Some(value)) = (field.kind, self.number(field.name))
                && !(min..=max).contains(&value)
            {
                errors.insert(field.name, range_error(min, max));
            }
        }
        if !errors.contains_key("critical_threshold") && self.critical_threshold >= self.low_threshold {
            errors.insert("critical_threshold", THRESHOLD_ERROR.to_string());
        }
        errors
    }

    pub fn is_enabled(&self, device_name: &str) -> bool {
        !self.disabled_devices.contains(device_name)
    }

    pub fn load() -> Self {
        Self::load_from(&config_file())
    }

    /// Load settings, falling back to the default of every missing or invalid value.
    pub fn load_from(path: &Path) -> Self {
        let text = match fs::read_to_string(path) {
            Ok(text) => text,
            Err(e) if e.kind() == io::ErrorKind::NotFound => return Self::default(),
            Err(e) => {
                tracing::warn!("Invalid settings file {}, using defaults: {e}", path.display());
                return Self::default();
            }
        };
        let table = match text.parse::<toml::Table>() {
            Ok(table) => table,
            Err(e) => {
                tracing::warn!("Invalid settings file {}, using defaults: {e}", path.display());
                return Self::default();
            }
        };

        let mut settings = Self::default();
        for field in FIELDS {
            let Some(value) = table.get(field.name) else {
                continue;
            };
            match (field.kind, value) {
                (FieldKind::Number { .. }, Value::Integer(number)) => settings.set_number(field.name, *number),
                (FieldKind::Checklist, Value::Array(items)) if items.iter().all(Value::is_str) => {
                    settings.disabled_devices = items.iter().filter_map(Value::as_str).map(String::from).collect();
                }
                _ => tracing::warn!("Invalid setting {}={value}, using default", field.name),
            }
        }

        let errors = settings.validate();
        if !errors.is_empty() {
            tracing::warn!("Invalid settings, using defaults for: {errors:?}");
            for name in errors.keys() {
                settings.reset(name);
            }
        }
        // Resetting one field may still conflict with another one: give up on the whole file
        if settings.validate().is_empty() { settings } else { Self::default() }
    }

    pub fn save(&self) -> io::Result<()> {
        self.save_to(&config_file())
    }

    /// Write atomically, so a crash never leaves a half-written file.
    pub fn save_to(&self, path: &Path) -> io::Result<()> {
        let text = toml::to_string_pretty(self).map_err(io::Error::other)?;
        let temp_path = path.with_extension("tmp");
        fs::write(&temp_path, text)?;
        fs::rename(&temp_path, path)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn config_path() -> (tempfile::TempDir, std::path::PathBuf) {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.toml");
        (dir, path)
    }

    fn with_low_threshold(low_threshold: i64) -> Settings {
        Settings { low_threshold, ..Settings::default() }
    }

    #[test]
    fn missing_file_uses_defaults() {
        let (_dir, path) = config_path();
        assert_eq!(Settings::load_from(&path), Settings::default());
    }

    #[test]
    fn save_and_load_round_trip() {
        let (_dir, path) = config_path();
        let settings = Settings {
            check_interval_minutes: 5,
            low_threshold: 30,
            disabled_devices: ["Mouse".to_string(), "Headset".to_string()].into(),
            ..Settings::default()
        };
        settings.save_to(&path).unwrap();

        assert_eq!(Settings::load_from(&path), settings);
        let text = fs::read_to_string(&path).unwrap();
        assert!(text.contains("disabled_devices = [\n    \"Headset\",\n    \"Mouse\",\n]"), "{text}");
    }

    #[test]
    fn invalid_toml_uses_defaults() {
        let (_dir, path) = config_path();
        fs::write(&path, "check_interval_minutes = ").unwrap();
        assert_eq!(Settings::load_from(&path), Settings::default());
    }

    #[test]
    fn invalid_value_uses_its_default() {
        for content in [
            "check_interval_minutes = 0",    // below min
            "check_interval_minutes = '5'",  // wrong type
            "check_interval_minutes = true", // bool is not an int
            "disabled_devices = 'Mouse'",    // not a list
        ] {
            let (_dir, path) = config_path();
            fs::write(&path, format!("low_threshold = 30\n{content}")).unwrap();
            assert_eq!(Settings::load_from(&path), with_low_threshold(30), "{content}");
        }
    }

    #[test]
    fn conflicting_thresholds_use_defaults() {
        let (_dir, path) = config_path();
        fs::write(&path, "low_threshold = 15\ncritical_threshold = 15").unwrap();
        assert_eq!(Settings::load_from(&path), with_low_threshold(15));
    }

    #[test]
    fn unknown_keys_are_ignored() {
        let (_dir, path) = config_path();
        fs::write(&path, "theme = 'dark'\nlow_threshold = 30").unwrap();
        assert_eq!(Settings::load_from(&path), with_low_threshold(30));
    }

    #[test]
    fn validate() {
        assert!(Settings::default().validate().is_empty());
        let settings = Settings { low_threshold: 60, critical_threshold: 50, ..Settings::default() };
        assert!(settings.validate().is_empty());
        assert_eq!(
            with_low_threshold(100).validate(),
            Errors::from([("low_threshold", "Must be between 1 and 99".to_string())])
        );
        let settings = Settings { critical_threshold: 20, ..Settings::default() };
        assert_eq!(settings.validate(), Errors::from([("critical_threshold", THRESHOLD_ERROR.to_string())]));
    }
}
