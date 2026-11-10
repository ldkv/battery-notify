# battery-notify

Windows and macOS tray app showing the battery level of HID and Bluetooth devices. A Rust Cargo package at the repository root; run checks with `task check-all` (see `Taskfile.yml`).

## Architecture

- `src/core/`: pure logic (devices, providers, poller, policy, settings), no GUI and no OS calls, so it stays testable on Linux and reusable by a future headless mode.
- `src/platforms/`: one module per OS behind the `Platform` trait, whose defaults are the unsupported-OS fallback. Reach OS code only through `current_platform()`.
- `src/ui/`: tray icon and menu (`tray-icon` on a `tao` event loop), icon renderer, `egui` settings dialog.
- The settings dialog runs in its own process (`battery-notifier settings`); exit code 0 means saved, and the tray then reloads `config.toml`. The tray holds the dialog's stdin (`--close-with-tray`): the dialog closes when the tray quits.
- A setting is one entry of `FIELDS` in `src/core/settings.rs`; the dialog is generated from it. Supported kinds are in `FieldKind`.
- Settings, the seen devices file and the single-instance lock keep the paths of earlier releases, so updates keep the user's files. Non-Windows single instance is a `flock` on `<state_dir>/<name>.lock`.

## Icons

The app icon (Windows executable, macOS app, settings dialog, notifications) comes from `assets/app-icon.svg`. After editing it, regenerate the committed `.png`, `.ico` and `.icns` beside it: `uvx --from cairosvg --with pillow python scripts/render_app_icon.py`.

The tray icon is separate: a live battery glyph.

Glyphs come from Segoe Fluent Icons / Segoe MDL2 Assets: `Battery0`–`Battery9` are U+E850–U+E859, but `Battery10` is U+E83F (U+E85A is a charging glyph).

## Seeing the GUI

Linux lacks Segoe UI, so judge the look from Windows: the `build` workflow uploads screenshots as artifacts, `settings-dialog-screenshot` (Windows) and `macos-settings-dialog-screenshot`. Fetch them with `gh run download <run-id> -n <artifact>` and look at them before claiming a UI change works.

## CI and releases

- The `ci` workflow runs `cargo fmt --check`, clippy and the tests on Ubuntu, Windows and macOS.
- The `build` workflow builds and smoke tests the Windows exe and, on `main`, releases and manual runs (`gh workflow run build.yml --ref <branch>`), the macOS app (`macos/bundle.sh`: universal binary through `lipo`, ad-hoc signed). The windowed exe has no stderr: errors only show in the log under `%LOCALAPPDATA%\battery-notifier\Logs`.
- release-please has one package at the root, tagged `v<version>` without component, which the updater looks for; the workflow syncs `Cargo.lock` in each release PR. The release workflow calls `build` for the created tag and publishes the Windows zip and macOS app with `SHA256SUMS.txt`.
- Release file names (`battery_notifier_rust-<version>-<platform>.zip`) are what installed apps' updater looks for: renaming them breaks updates of released apps.

## macOS

The tray runs with the `Accessory` activation policy (no Dock icon) but the settings dialog does not, so it can take focus. Notifications go through `UNUserNotificationCenter` from the app bundle (which macOS only allows from Applications or `~/Applications`), and through `osascript` without a bundle, where `UNUserNotificationCenter` would raise an exception.

## Updates

`src/updater.rs` checks the latest release daily (release builds only, unless `check_for_updates` is off), verifies the zip's zipsign signature for its file name against `updater-key.pub`, and installs the versioned exe next to the running one, which the new version deletes once started with `--after-update <previous exe>`, or replaces the whole `.app` (renaming the bundle: replacing only the binary would break its signature). The release workflow signs the zips with the `ZIPSIGN_PRIVATE_KEY` secret; the Windows exe ships zipped for that reason.

## Commits

Conventional commits (`feat:`, `fix:`, `perf:`, ...): release-please derives versions and release notes from them.
