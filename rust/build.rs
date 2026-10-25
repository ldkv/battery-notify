//! Embed the app icon in the Windows executable, shown by Explorer and the taskbar.
//! winresource is a Windows-only build dependency: Windows executables are built on Windows.

fn main() {
    println!("cargo::rerun-if-changed=../src/battery_notifier/assets/app-icon.ico");
    #[cfg(windows)]
    {
        let mut resource = winresource::WindowsResource::new();
        resource.set_icon("../src/battery_notifier/assets/app-icon.ico");
        resource.compile().expect("compile the Windows resources");
    }
}
