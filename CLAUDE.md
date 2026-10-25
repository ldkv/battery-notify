# battery-notify

Windows tray app showing the battery level of HID and Bluetooth devices. Python, managed with uv; run checks with `task check-all` (see `Taskfile.yml`).

## Architecture

- `core/`: pure logic (devices, providers, poller, policy, settings), no GUI and no OS calls, so it stays testable on Linux and reusable by a future headless mode.
- `platforms/`: one module per OS behind the `Platform` base class, whose defaults are the unsupported-OS fallback. Reach Windows code only through `current_platform()`. The package is `platforms`, plural: the build puts `src/battery_notifier` on `sys.path`, where a `platform` package would shadow the stdlib module.
- `ui/`: pystray tray, icon renderer, tk settings dialog.
- The settings dialog runs in its own process (`battery-notifier settings`); exit code 0 means saved, and the tray then reloads `config.toml`.

## Windows-only code

Windows is the target: pyrefly checks the whole project with `python-platform = "win32"`, Windows-only dependencies carry `sys_platform == 'win32'` markers, and tests needing Windows or a display skip themselves elsewhere. CI runs on Ubuntu and Windows.

## Settings and dialog

- A setting is one `setting(...)` field on `Settings`; the dialog form is generated from it. Supported types are `int` and `frozenset[str]`; a new type needs a branch in `settings._parse` and `ui/form.py`.
- sv_ttk recolors every existing widget (`tk_setPalette`) once the theme change is processed, so the dialog applies the theme before creating any widget, then sets label colors and entry fonts per widget: custom ttk styles lose to sv_ttk.
- The dialog never resizes or moves fields: `fix_size` sizes the window for the longest possible error message, shown on one status line. A new error message must be added there; `tests/test_settings_dialog.py` checks the layout stays put.

## Icons

The app icon (Windows executables, macOS app, settings dialog, Rust notifications) comes from `src/battery_notifier/assets/app-icon.svg`. After editing it, regenerate the committed `.png`, `.ico` and `.icns` beside it, used by both versions: `uvx --from cairosvg --with pillow python scripts/render_app_icon.py`.

The tray icon is separate: a live battery glyph.

Glyphs come from Segoe Fluent Icons / Segoe MDL2 Assets: `Battery0`–`Battery9` are U+E850–U+E859, but `Battery10` is U+E83F (U+E85A is a charging glyph).

## Seeing the GUI

Check layout locally under Xvfb: `DIALOG_SCREENSHOTS=shots xvfb-run -a uv run pytest tests/test_settings_dialog.py` saves the dialog with each error shown. Linux lacks Segoe UI, so judge the look from Windows: the CI jobs upload screenshots as artifacts, `settings-dialog-errors` and `tray-icons` (ci workflow), `settings-dialog-screenshot` (build workflow). Fetch them with `gh run download <run-id> -n <artifact>` and look at them before claiming a UI change works.

## Build

`task generate-executable` builds one Nuitka onefile exe (Windows only):

- Unpacked once per version to `%LOCALAPPDATA%\battery-notifier\app\<version>`; `UNPACK_ROOT` in `launcher.py` must match `--onefile-tempdir-spec`.
- `scripts/tcl_tk_libraries.py` extracts the Tcl/Tk libraries that uv's standalone Python zips inside its DLLs, where Nuitka cannot find them. The build workflow uses uv's Python (`UV_PYTHON_PREFERENCE=only-managed`) to match developer machines.
- `--include-package=winrt`: winrt submodules are imported from native code, invisible to Nuitka. `--include-package-data=winrt`: since winrt 4, each projection reads its `_table.pywinrt` at import; without it the exe dies at startup, before logging anything.
- The windowed exe has no stderr: errors only show in the log under `%LOCALAPPDATA%\battery-notifier\Logs`.

## Rust port

`rust/` is a standalone Cargo package porting the app, same module layout, released alongside Python: the release workflow calls `python-build-windows` and `rust-build` for the tag, then publishes the Python and Rust Windows executables, the macOS app and `SHA256SUMS.txt`. One version for both: release-please bumps `rust/Cargo.toml` through `extra-files`, and the release PR syncs `uv.lock` and `rust/Cargo.lock`. It shares `config.toml`, the seen devices file and the single-instance mutex with the Python version. Checks: `task rust-check` and `task rust-test`, run by the `rust-ci` workflow; the `rust-build` workflow builds and smoke tests the Windows exe and, on `main` and releases, the macOS app (`rust/macos/bundle.sh`: universal binary through `lipo`, ad-hoc signed). On macOS, the tray runs with the `Accessory` activation policy (no Dock icon) but the settings dialog does not, so it can take focus; notifications go through `UNUserNotificationCenter` from the app bundle (which macOS only allows from Applications or `~/Applications`), and through `osascript` without a bundle, where `UNUserNotificationCenter` would raise an exception. Non-Windows single instance is a `flock` on `<state_dir>/<name>.lock`. When changing a feature, change both versions until Python is retired.

## Commits

Conventional commits (`feat:`, `fix:`, `perf:`, ...): release-please derives versions and release notes from them.
