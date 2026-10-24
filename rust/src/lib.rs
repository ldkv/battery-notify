//! Notify when the battery of a device is low.

pub mod core;
pub mod logs;
pub mod platforms;
pub mod ui;

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
