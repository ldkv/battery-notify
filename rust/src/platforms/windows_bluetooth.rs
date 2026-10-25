//! Battery level of connected Bluetooth devices, as shown in Windows Settings.
//! Reads the PnP device properties through WinRT, in process.

use std::collections::BTreeSet;

/// "Is connected" property, source: <https://stackoverflow.com/a/71609867/21333661>
#[cfg_attr(not(windows), allow(dead_code))]
const CONNECTED_KEY: &str = "{83DA6326-97A6-4088-9453-A1923F573B29} 15";
#[cfg_attr(not(windows), allow(dead_code))]
const BATTERY_KEY: &str = "{104EA319-6EE2-4701-BD47-8DDBF425BBE5} 2";
#[cfg_attr(not(windows), allow(dead_code))]
const BLUETOOTH_DEVICES: &str = r#"System.Devices.ClassGuid:="{e0cbf06c-cd8b-4647-bb8a-263b43f0f974}""#;
const IGNORED_TEXTS: [&str; 3] = ["Generic", "Service", "Bluetooth"];
// DualSense has its own HID driver
const IGNORED_DEVICES: [&str; 2] = ["microsoft bluetooth device", "dualsense wireless controller"];

pub fn connected_device_names(devices: &[(String, bool)]) -> BTreeSet<String> {
    devices
        .iter()
        .filter(|(name, connected)| {
            *connected
                && !IGNORED_TEXTS.iter().any(|text| name.contains(text))
                && !IGNORED_DEVICES.contains(&name.to_lowercase().as_str())
        })
        .map(|(name, _)| name.clone())
        .collect()
}

/// Battery level of each named device, read from the first device node whose name contains it.
pub fn match_batteries(names: &BTreeSet<String>, batteries: &[(String, u8)]) -> Vec<(String, u8)> {
    names
        .iter()
        .filter_map(|name| {
            let (_, level) = batteries.iter().find(|(node_name, _)| node_name.contains(name.as_str()))?;
            Some((name.clone(), *level))
        })
        .collect()
}

#[cfg(windows)]
pub fn bluetooth_batteries() -> Vec<(String, u8)> {
    match winrt::find_bluetooth_batteries() {
        Ok(found) => {
            tracing::info!("Bluetooth battery levels: {found:?}");
            found
        }
        Err(e) => {
            tracing::error!("Error reading Bluetooth devices: {e}");
            Vec::new()
        }
    }
}

#[cfg(windows)]
mod winrt {
    use windows::Devices::Enumeration::{DeviceInformation, DeviceInformationKind};
    use windows::Foundation::IPropertyValue;
    use windows::core::{HSTRING, Interface, Result};

    use super::{BATTERY_KEY, BLUETOOTH_DEVICES, CONNECTED_KEY, connected_device_names, match_batteries};

    pub fn find_bluetooth_batteries() -> Result<Vec<(String, u8)>> {
        let bluetooth = find_devices(BLUETOOTH_DEVICES, CONNECTED_KEY, IPropertyValue::GetBoolean)?;
        let names = connected_device_names(&bluetooth);
        // The battery level is often on another device node of the same device, e.g. "<name> Hands-Free AG"
        let batteries = find_devices("", BATTERY_KEY, IPropertyValue::GetUInt8)?;
        Ok(match_batteries(&names, &batteries))
    }

    /// Name and property value of the device nodes that have the property.
    fn find_devices<T>(
        aqs_filter: &str,
        key: &str,
        unbox: impl Fn(&IPropertyValue) -> Result<T>,
    ) -> Result<Vec<(String, T)>> {
        let properties: Vec<HSTRING> = vec![key.into()];
        let devices = DeviceInformation::FindAllAsyncWithKindAqsFilterAndAdditionalProperties(
            &aqs_filter.into(),
            &windows_collections::IIterable::from(properties),
            DeviceInformationKind::Device,
        )?
        .join()?;
        let key = HSTRING::from(key);
        let mut found = Vec::new();
        for device in devices {
            let properties = device.Properties()?;
            // A missing or null value is an error, the null one with code 0: the node has no such property
            let Ok(value) = properties.Lookup(&key).and_then(|value| value.cast::<IPropertyValue>()) else {
                continue;
            };
            if let Ok(value) = unbox(&value) {
                found.push((device.Name()?.to_string(), value));
            }
        }
        Ok(found)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn connected_device_names_skips_disconnected_and_system_devices() {
        let devices: Vec<_> = [
            ("WH-1000XM4", true),
            ("MX Keys", false),
            ("Microsoft Bluetooth Enumerator", true),
            ("Generic Attribute Profile", true),
            ("DualSense Wireless Controller", true),
        ]
        .into_iter()
        .map(|(name, connected)| (name.to_string(), connected))
        .collect();
        assert_eq!(connected_device_names(&devices), BTreeSet::from(["WH-1000XM4".to_string()]));
    }

    #[test]
    fn match_batteries_reads_level_from_any_node_containing_the_name() {
        let batteries = [("Other Speaker".to_string(), 10), ("WH-1000XM4 Hands-Free AG".to_string(), 70)];
        let names = BTreeSet::from(["WH-1000XM4".to_string(), "MX Keys".to_string()]);
        assert_eq!(match_batteries(&names, &batteries), [("WH-1000XM4".to_string(), 70)]);
    }

    /// No Bluetooth device on CI runners: checks the WinRT calls themselves.
    #[cfg(windows)]
    #[test]
    fn bluetooth_batteries_runs() {
        winrt::find_bluetooth_batteries().unwrap();
    }
}
