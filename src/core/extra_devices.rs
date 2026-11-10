//! Devices the user adds in `extra-devices.toml`: the battery method of a built-in device, tried on another
//! VID, PID or HID interface, e.g. a sibling model from the same manufacturer.
//!
//! ```toml
//! [[devices]]
//! name = "Keychron M7"
//! same_as = "Keychron M6"   # built-in device whose battery method to use
//! pid = 0xD029              # vid, pid, usage_page, usage, interface: optional, default to same_as's
//! ```

use std::borrow::Cow;
use std::path::Path;
use std::{fs, io};

use serde::Deserialize;

use crate::core::devices::{DeviceType, Filter, HID_DEVICES};

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Entry {
    name: String,
    same_as: String,
    vid: Option<u16>,
    pid: Option<u16>,
    usage_page: Option<u16>,
    usage: Option<u16>,
    interface: Option<i32>,
}

/// The built-in devices, then the valid entries of the extra devices file when given.
pub fn device_types(extra_devices_file: Option<&Path>) -> Vec<DeviceType> {
    let mut device_types = HID_DEVICES.to_vec();
    if let Some(path) = extra_devices_file {
        device_types.extend(load(path));
    }
    device_types
}

/// Read on each poll, so edits apply from the next check: empty when the file is missing or unreadable.
pub fn load(path: &Path) -> Vec<DeviceType> {
    match fs::read_to_string(path) {
        Ok(text) => parse(&text),
        Err(e) if e.kind() == io::ErrorKind::NotFound => Vec::new(),
        Err(e) => {
            tracing::warn!("Could not read {}: {e}", path.display());
            Vec::new()
        }
    }
}

/// Invalid entries are logged and skipped, the others are kept.
pub fn parse(text: &str) -> Vec<DeviceType> {
    let table = match text.parse::<toml::Table>() {
        Ok(table) => table,
        Err(e) => {
            tracing::warn!("Invalid extra devices file, ignored: {e}");
            return Vec::new();
        }
    };
    let Some(entries) = table.get("devices").and_then(toml::Value::as_array) else {
        return Vec::new();
    };
    let mut device_types = Vec::new();
    for value in entries {
        match value.clone().try_into::<Entry>().map_err(|e| e.to_string()).and_then(|e| device_type(e, &device_types)) {
            Ok(device_type) => device_types.push(device_type),
            Err(e) => tracing::warn!("Invalid extra device, skipped: {e}"),
        }
    }
    device_types
}

fn device_type(entry: Entry, added: &[DeviceType]) -> Result<DeviceType, String> {
    if HID_DEVICES.iter().chain(added).any(|device_type| device_type.name == entry.name) {
        return Err(format!("{}: a device with this name already exists", entry.name));
    }
    let base = HID_DEVICES
        .iter()
        .find(|device_type| device_type.name == entry.same_as)
        .ok_or_else(|| format!("{}: unknown same_as \"{}\"", entry.name, entry.same_as))?;
    Ok(DeviceType {
        name: Cow::Owned(entry.name),
        vid: entry.vid.unwrap_or(base.vid),
        pid: entry.pid.unwrap_or(base.pid),
        filter: Filter {
            usage_page: entry.usage_page.or(base.filter.usage_page),
            usage: entry.usage.or(base.filter.usage),
            interface_number: entry.interface.or(base.filter.interface_number),
        },
        driver: base.driver,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::devices::mouse::{KEYCHRON_M6, RAZER_PRO_CLICK_MINI};

    const M7: &str = r#"
        [[devices]]
        name = "Keychron M7"
        same_as = "Keychron M6"
        pid = 0xD029
    "#;

    fn names(device_types: &[DeviceType]) -> Vec<&str> {
        device_types.iter().map(|device_type| &*device_type.name).collect()
    }

    #[test]
    fn entry_uses_the_method_and_identity_of_same_as_unless_overridden() {
        let [m7] = parse(M7).try_into().unwrap_or_else(|_| panic!("one device expected"));
        assert_eq!(m7.name, "Keychron M7");
        assert_eq!((m7.vid, m7.pid), (KEYCHRON_M6.vid, 0xD029));
        assert_eq!(m7.filter, KEYCHRON_M6.filter);
        assert!(std::ptr::fn_addr_eq(m7.driver, KEYCHRON_M6.driver));
    }

    #[test]
    fn entry_overrides_the_interface() {
        let text = r#"
            [[devices]]
            name = "Razer other"
            same_as = "Razer Pro Click Mini"
            vid = 0x1234
            usage_page = 0xFF00
            usage = 1
            interface = 2
        "#;
        let [razer] = parse(text).try_into().unwrap_or_else(|_| panic!("one device expected"));
        assert_eq!((razer.vid, razer.pid), (0x1234, RAZER_PRO_CLICK_MINI.pid));
        assert_eq!(razer.filter, Filter { usage_page: Some(0xFF00), usage: Some(1), interface_number: Some(2) });
    }

    #[test]
    fn invalid_entries_are_skipped() {
        let entry = |fields: &str| format!("[[devices]]\n{fields}\n");
        let text = [
            entry(
                r#"name = "Unknown method"
                     same_as = "Logitech G502""#,
            ),
            entry(
                r#"name = "Keychron M6"
                     same_as = "Razer Pro Click Mini""#,
            ), // built-in name
            entry(
                r#"name = "Keychron M7"
                     same_as = "Keychron M6""#,
            ),
            entry(
                r#"name = "Keychron M7"
                     same_as = "Keychron M6""#,
            ), // duplicate in the file
            entry(
                r#"name = "Typo"
                     same_as = "Keychron M6"
                     PID = 0xD029"#,
            ),
            entry(
                r#"name = "Too large"
                     same_as = "Keychron M6"
                     pid = 0x10000"#,
            ),
            entry(r#"name = "No method""#),
        ]
        .concat();
        assert_eq!(names(&parse(&text)), ["Keychron M7"]);
    }

    #[test]
    fn invalid_file_is_ignored() {
        assert!(parse("[[devices]\nname =").is_empty());
        assert!(parse("").is_empty());
    }

    #[test]
    fn device_types_add_the_file_to_the_built_in_devices() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("extra-devices.toml");
        let built_in: Vec<_> = HID_DEVICES.iter().map(|device_type| &*device_type.name).collect();
        assert_eq!(names(&device_types(Some(&path))), built_in, "missing file");
        assert_eq!(names(&device_types(None)), built_in);

        fs::write(&path, M7).unwrap();
        assert_eq!(names(&device_types(Some(&path))), [built_in, vec!["Keychron M7"]].concat());
    }
}
