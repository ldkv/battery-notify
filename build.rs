//! Embed the app icon in the Windows executable, shown by Explorer and the taskbar.
//! winresource is a Windows-only build dep: Windows executables are built on Windows.

fn main() {
    println!("cargo::rerun-if-changed=assets/app-icon.ico");
    #[cfg(windows)]
    {
        let mut resource = winresource::WindowsResource::new();
        resource.set_icon("assets/app-icon.ico");
        // Shown as the app name in Task Manager, which otherwise takes the package description
        resource.set("FileDescription", "Battery Notifier");
        resource.compile().expect("compile the Windows resources");
    }
}
