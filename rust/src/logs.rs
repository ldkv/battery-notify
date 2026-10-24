use tracing_appender::rolling::{RollingFileAppender, Rotation};
use tracing_subscriber::fmt::writer::MakeWriterExt;

use crate::core::paths::log_dir;

/// Separate from the Python version's `battery_notifier.log`, in the same folder.
const LOG_FILE_PREFIX: &str = "battery_notifier_rust";
const MAX_LOG_FILES: usize = 7;

/// Log to the console and to a daily log file, written synchronously so that nothing is lost on exit.
pub fn configure_logging() {
    let file = RollingFileAppender::builder()
        .rotation(Rotation::DAILY)
        .filename_prefix(LOG_FILE_PREFIX)
        .filename_suffix("log")
        .max_log_files(MAX_LOG_FILES)
        .build(log_dir());

    let builder = tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .with_ansi(false)
        .with_thread_names(true)
        .with_file(true)
        .with_line_number(true);
    match file {
        Ok(file) => builder.with_writer(std::io::stderr.and(file)).init(),
        Err(e) => {
            builder.with_writer(std::io::stderr).init();
            tracing::error!("Could not open the log file: {e}");
        }
    }
}
