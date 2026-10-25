//! Update the app from its GitHub releases: find a newer release, download this platform's zip,
//! verify the signature it embeds, then replace the running app (the executable on Windows, the
//! whole `.app` bundle on macOS). Other OSes do not update themselves.

use std::fs::{self, File};
use std::io;
use std::path::{Path, PathBuf};

use serde::Deserialize;
use zipsign_api::{PUBLIC_KEY_LENGTH, VerifyingKey};

use crate::VERSION;
use crate::core::paths::state_dir;

const LATEST_RELEASE_URL: &str = "https://api.github.com/repos/ldkv/battery-notify/releases/latest";
pub const RELEASES_PAGE: &str = "https://github.com/ldkv/battery-notify/releases/latest";
/// Public half of the key the release workflow signs the zips with: see the README.
const PUBLIC_KEY: &[u8; PUBLIC_KEY_LENGTH] = include_bytes!("../updater-key.pub");
/// Command line flag of the updated app: wait for the previous one to exit instead of quitting.
pub const AFTER_UPDATE_FLAG: &str = "--after-update";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AvailableUpdate {
    pub version: String,
    asset_name: String,
    download_url: String,
}

#[derive(Deserialize)]
struct Release {
    tag_name: String,
    assets: Vec<Asset>,
}

#[derive(Deserialize)]
struct Asset {
    name: String,
    browser_download_url: String,
}

/// Name of the released zip for this platform, None where the app does not update itself.
fn asset_name(version: &str) -> Option<String> {
    let platform = if cfg!(windows) {
        "windows-x64"
    } else if cfg!(target_os = "macos") {
        "macos"
    } else {
        return None;
    };
    Some(format!("battery_notifier_rust-{version}-{platform}.zip"))
}

/// Whether `candidate` is a later `major.minor.patch` version than `current`.
fn is_newer(candidate: &str, current: &str) -> bool {
    let parse = |version: &str| -> Option<Vec<u64>> { version.split('.').map(|part| part.parse().ok()).collect() };
    match (parse(candidate), parse(current)) {
        (Some(candidate), Some(current)) => candidate > current,
        _ => false,
    }
}

fn find_update(release: Release, current: &str) -> Option<AvailableUpdate> {
    let version = release.tag_name.trim_start_matches('v').to_string();
    if !is_newer(&version, current) {
        return None;
    }
    let asset_name = asset_name(&version)?;
    let asset = release.assets.into_iter().find(|asset| asset.name == asset_name)?;
    Some(AvailableUpdate { version, asset_name, download_url: asset.browser_download_url })
}

fn agent() -> ureq::Agent {
    ureq::Agent::config_builder().user_agent(format!("battery-notifier/{VERSION}")).build().into()
}

/// The latest release if it is newer than this app and has a zip for this platform.
pub fn check() -> io::Result<Option<AvailableUpdate>> {
    if asset_name(VERSION).is_none() {
        return Ok(None);
    }
    let release: Release =
        agent().get(LATEST_RELEASE_URL).call().and_then(|mut r| r.body_mut().read_json()).map_err(io::Error::other)?;
    Ok(find_update(release, VERSION))
}

/// Check that `zip` carries a signature by one of `keys` for its file name, which the release workflow signs with.
fn verify(zip: &Path, asset_name: &str, keys: &[VerifyingKey]) -> io::Result<()> {
    let mut file = File::open(zip)?;
    zipsign_api::verify::verify_zip(&mut file, keys, Some(asset_name.as_bytes()))
        .map(|_| ())
        .map_err(|e| io::Error::new(io::ErrorKind::InvalidData, format!("invalid signature: {e}")))
}

/// Download and verify the update, replace the running app, and return the command to start the new one.
pub fn install(update: &AvailableUpdate) -> io::Result<std::process::Command> {
    let dir = state_dir().join("update");
    if dir.exists() {
        fs::remove_dir_all(&dir)?;
    }
    fs::create_dir_all(&dir)?;
    let zip = dir.join(&update.asset_name);
    let mut response = agent().get(&update.download_url).call().map_err(io::Error::other)?;
    io::copy(&mut response.body_mut().with_config().limit(200 * 1024 * 1024).reader(), &mut File::create(&zip)?)?;
    let key = VerifyingKey::from_bytes(PUBLIC_KEY).map_err(io::Error::other)?;
    verify(&zip, &update.asset_name, &[key])?;
    tracing::info!("Verified {}", update.asset_name);

    let extracted = dir.join("extracted");
    zip::ZipArchive::new(File::open(&zip)?)
        .and_then(|mut archive| archive.extract(&extracted))
        .map_err(io::Error::other)?;
    let command = replace_app(&extracted)?;
    let _ = fs::remove_dir_all(&dir);
    Ok(command)
}

#[cfg(windows)]
fn replace_app(extracted: &Path) -> io::Result<std::process::Command> {
    let new_exe = extracted.join("battery-notifier.exe");
    self_replace::self_replace(&new_exe)?;
    let mut command = std::process::Command::new(std::env::current_exe()?);
    command.arg(AFTER_UPDATE_FLAG);
    Ok(command)
}

#[cfg(target_os = "macos")]
fn replace_app(extracted: &Path) -> io::Result<std::process::Command> {
    let bundle = running_bundle(&std::env::current_exe()?)
        .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "not running from an app bundle"))?;
    let new_bundle = extracted.join(bundle.file_name().unwrap_or_default());
    swap_bundle(&bundle, &new_bundle)?;
    let mut command = std::process::Command::new("open");
    command.arg("-n").arg(&bundle).arg("--args").arg(AFTER_UPDATE_FLAG);
    Ok(command)
}

#[cfg(not(any(windows, target_os = "macos")))]
fn replace_app(_extracted: &Path) -> io::Result<std::process::Command> {
    Err(io::Error::new(io::ErrorKind::Unsupported, "updates are not supported on this OS"))
}

/// The `.app` bundle containing `exe`, i.e. `<bundle>.app/Contents/MacOS/<exe>`.
#[cfg_attr(not(target_os = "macos"), allow(dead_code))]
fn running_bundle(exe: &Path) -> Option<PathBuf> {
    let bundle = exe.parent()?.parent()?.parent()?;
    (bundle.extension()? == "app").then(|| bundle.to_path_buf())
}

/// Put `new_bundle` in place of `bundle`, keeping the old one until the new one is in place.
#[cfg_attr(not(target_os = "macos"), allow(dead_code))]
fn swap_bundle(bundle: &Path, new_bundle: &Path) -> io::Result<()> {
    let old = bundle.with_extension("app.old");
    if old.exists() {
        fs::remove_dir_all(&old)?;
    }
    fs::rename(bundle, &old)?;
    if let Err(e) = fs::rename(new_bundle, bundle) {
        let _ = fs::rename(&old, bundle);
        return Err(e);
    }
    let _ = fs::remove_dir_all(&old);
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::io::{Cursor, Write};

    use zipsign_api::SigningKey;
    use zipsign_api::sign::copy_and_sign_zip;

    use super::*;

    #[test]
    fn versions() {
        assert!(is_newer("0.5.0", "0.4.0"));
        assert!(is_newer("0.10.0", "0.9.9"));
        assert!(is_newer("1.0.0", "0.99.0"));
        assert!(!is_newer("0.4.0", "0.4.0"));
        assert!(!is_newer("0.3.9", "0.4.0"));
        assert!(!is_newer("0.5.0-beta", "0.4.0"));
    }

    fn release(tag: &str, names: &[&str]) -> Release {
        let assets = names
            .iter()
            .map(|name| Asset {
                name: (*name).to_string(),
                browser_download_url: format!("https://example.com/{name}"),
            })
            .collect();
        Release { tag_name: tag.to_string(), assets }
    }

    #[test]
    fn finds_this_platform_zip_of_a_newer_release() {
        let Some(name) = asset_name("9.0.0") else { return }; // no updates on this OS
        let found = find_update(release("v9.0.0", &["battery_notifier-9.0.0-windows-x64.exe", &name]), "0.4.0");
        assert_eq!(found.map(|update| update.asset_name), Some(name));
        assert_eq!(find_update(release("v0.4.0", &[]), "0.4.0"), None);
        assert_eq!(find_update(release("v9.0.0", &["SHA256SUMS.txt"]), "0.4.0"), None);
    }

    fn signed_zip(dir: &Path, name: &str, key: &SigningKey, context: &str) -> PathBuf {
        let mut plain = Cursor::new(Vec::new());
        let mut writer = zip::ZipWriter::new(&mut plain);
        writer.start_file("battery-notifier.exe", zip::write::SimpleFileOptions::default()).unwrap();
        writer.write_all(b"new version").unwrap();
        writer.finish().unwrap();
        plain.set_position(0);
        let mut signed = Cursor::new(Vec::new());
        copy_and_sign_zip(&mut plain, &mut signed, std::slice::from_ref(key), Some(context.as_bytes())).unwrap();
        let path = dir.join(name);
        fs::write(&path, signed.into_inner()).unwrap();
        path
    }

    #[test]
    fn signature_must_match_the_key_and_the_file_name() {
        let dir = tempfile::tempdir().unwrap();
        let key = SigningKey::from_bytes(&[7; 32]);
        let other = SigningKey::from_bytes(&[8; 32]);
        let name = "battery_notifier_rust-9.0.0-windows-x64.zip";

        let zip = signed_zip(dir.path(), name, &key, name);
        assert!(verify(&zip, name, &[key.verifying_key()]).is_ok());
        // The signature is a prefix that zip readers skip, as the updater does once verified
        let mut archive = zip::ZipArchive::new(File::open(&zip).unwrap()).unwrap();
        let mut content = String::new();
        io::Read::read_to_string(&mut archive.by_name("battery-notifier.exe").unwrap(), &mut content).unwrap();
        assert_eq!(content, "new version");
        assert!(verify(&zip, name, &[other.verifying_key()]).is_err());
        assert!(verify(&zip, "battery_notifier_rust-9.0.0-macos.zip", &[key.verifying_key()]).is_err());

        let unsigned = dir.path().join("unsigned.zip");
        fs::write(&unsigned, b"PK\x05\x06").unwrap();
        assert!(verify(&unsigned, name, &[key.verifying_key()]).is_err());
    }

    #[test]
    fn running_bundle_of_an_executable() {
        let exe = Path::new("/Applications/Battery Notifier.app/Contents/MacOS/battery-notifier");
        assert_eq!(running_bundle(exe), Some(PathBuf::from("/Applications/Battery Notifier.app")));
        assert_eq!(running_bundle(Path::new("/usr/local/bin/battery-notifier")), None);
    }

    #[test]
    fn swap_bundle_replaces_the_app_and_removes_the_old_one() {
        let dir = tempfile::tempdir().unwrap();
        let bundle = dir.path().join("Battery Notifier.app");
        let new_bundle = dir.path().join("extracted/Battery Notifier.app");
        fs::create_dir_all(bundle.join("Contents")).unwrap();
        fs::write(bundle.join("Contents/version"), "old").unwrap();
        fs::create_dir_all(new_bundle.join("Contents")).unwrap();
        fs::write(new_bundle.join("Contents/version"), "new").unwrap();

        swap_bundle(&bundle, &new_bundle).unwrap();
        assert_eq!(fs::read_to_string(bundle.join("Contents/version")).unwrap(), "new");
        assert!(!dir.path().join("Battery Notifier.app.old").exists());
        assert!(!new_bundle.exists());
    }

    #[test]
    fn swap_bundle_keeps_the_app_when_the_new_one_is_missing() {
        let dir = tempfile::tempdir().unwrap();
        let bundle = dir.path().join("Battery Notifier.app");
        fs::create_dir_all(&bundle).unwrap();
        assert!(swap_bundle(&bundle, &dir.path().join("missing.app")).is_err());
        assert!(bundle.exists());
    }
}
