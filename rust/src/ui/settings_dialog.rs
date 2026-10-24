//! Settings dialog, generated from the settings `FIELDS`.
//! Runs in its own process: `battery-notifier settings`, exit code 0 when saved.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};

use eframe::egui::{
    self, Button, CentralPanel, Color32, IconData, Key, RichText, Stroke, StrokeKind, TextEdit, Theme, ViewportBuilder,
    ViewportCommand,
};

use crate::core::paths::{log_dir, seen_devices_file};
use crate::core::poller::known_device_names;
use crate::core::settings::{Errors, FIELDS, Field, FieldKind, Settings};
use crate::platforms::Platform;
use crate::ui::icon::{SIZE, icon_renderer};

const TITLE: &str = "Battery Notifier settings";
const WIDTH: f32 = 460.0;
const PADDING: i8 = 20;
const ROW_GAP: f32 = 12.0;
const NUMBER_WIDTH: f32 = 64.0;
pub const NOT_A_NUMBER: &str = "Must be a whole number";
// Windows 11 "critical" and caption text colors
const ERROR_COLORS: [Color32; 2] = [Color32::from_rgb(0xc4, 0x2b, 0x1c), Color32::from_rgb(0xff, 0x99, 0xa4)];
const CAPTION_COLORS: [Color32; 2] = [Color32::from_rgb(0x5d, 0x5d, 0x5d), Color32::from_rgb(0xa0, 0xa0, 0xa0)];

/// The dialog's state, independent of the GUI toolkit.
pub struct Form {
    settings: Settings,
    /// Text of each number field, in `FIELDS` order.
    pub numbers: Vec<(Field, String)>,
    /// Device name and whether it is enabled.
    pub devices: Vec<(String, bool)>,
}

impl Form {
    pub fn new(settings: Settings, device_names: Vec<String>) -> Self {
        let numbers =
            FIELDS.into_iter().filter_map(|field| Some((field, settings.number(field.name)?.to_string()))).collect();
        let devices = device_names
            .into_iter()
            .map(|name| {
                let enabled = settings.is_enabled(&name);
                (name, enabled)
            })
            .collect();
        Self { settings, numbers, devices }
    }

    /// Settings as edited, with an error message per invalid field.
    pub fn edited_settings(&self) -> (Settings, Errors) {
        let mut edited = self.settings.clone();
        let mut parse_errors = Errors::new();
        for (field, text) in &self.numbers {
            match text.trim().parse() {
                Ok(value) => edited.set_number(field.name, value),
                Err(_) => {
                    parse_errors.insert(field.name, NOT_A_NUMBER.to_string());
                }
            }
        }
        edited.disabled_devices =
            self.devices.iter().filter(|(_, enabled)| !enabled).map(|(name, _)| name.clone()).collect();
        let mut errors = edited.validate();
        errors.extend(parse_errors);
        (edited, errors)
    }
}

/// First error in field order, as shown below the form.
pub fn error_text(errors: &Errors) -> Option<String> {
    FIELDS.iter().find_map(|field| {
        let message = errors.get(field.name)?;
        let mut message = message.chars();
        let first = message.next().map(|first| first.to_lowercase().to_string()).unwrap_or_default();
        Some(format!("\u{26a0} {}: {first}{}", field.label, message.as_str()))
    })
}

struct SettingsDialog {
    platform: Arc<dyn Platform>,
    form: Form,
    autostart: bool,
    saved: Arc<AtomicBool>,
    dark: bool,
    ready: bool,
    height: f32,
}

impl SettingsDialog {
    fn save_settings(&self, ctx: &egui::Context) {
        let (settings, errors) = self.form.edited_settings();
        if !errors.is_empty() {
            return;
        }
        if let Err(e) = settings.save() {
            tracing::error!("Could not save the settings: {e}");
            return;
        }
        if self.platform.supports_autostart()
            && self.autostart != self.platform.is_autostart_enabled()
            && let Err(e) = self.platform.set_autostart(self.autostart)
        {
            tracing::error!("Could not change run at startup: {e}");
        }
        tracing::info!("Settings saved: {settings:?}");
        self.saved.store(true, Ordering::SeqCst);
        ctx.send_viewport_cmd(ViewportCommand::Close);
    }

    fn number_row(ui: &mut egui::Ui, field: &Field, text: &mut String, invalid: bool, colors: (Color32, Color32)) {
        let (error_color, caption_color) = colors;
        ui.horizontal(|ui| {
            ui.vertical(|ui| {
                ui.label(field.label);
                if !field.help.is_empty() {
                    ui.label(RichText::new(field.help).color(caption_color));
                }
            });
            ui.with_layout(egui::Layout::right_to_left(egui::Align::Min), |ui| {
                let response = ui.add(TextEdit::singleline(text).desired_width(NUMBER_WIDTH));
                if invalid {
                    ui.painter().rect_stroke(response.rect, 2.0, Stroke::new(1.5, error_color), StrokeKind::Outside);
                }
            });
        });
        ui.add_space(ROW_GAP);
    }
}

impl eframe::App for SettingsDialog {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let ctx = ui.ctx().clone();
        let colors = (ERROR_COLORS[usize::from(self.dark)], CAPTION_COLORS[usize::from(self.dark)]);
        let (_, errors) = self.form.edited_settings();

        let content = CentralPanel::default().frame(egui::Frame::central_panel(ui.style()).inner_margin(PADDING)).show(
            ui,
            |ui| {
                for (field, text) in &mut self.form.numbers {
                    Self::number_row(ui, field, text, errors.contains_key(field.name), colors);
                }
                if let Some(checklist) = FIELDS.iter().find(|field| field.kind == FieldKind::Checklist) {
                    ui.group(|ui| {
                        ui.set_width(ui.available_width());
                        ui.label(checklist.label);
                        ui.label(RichText::new(checklist.help).color(colors.1));
                        for (name, enabled) in &mut self.form.devices {
                            ui.checkbox(enabled, name.as_str());
                        }
                    });
                    ui.add_space(ROW_GAP);
                }
                if self.platform.supports_autostart() {
                    ui.checkbox(&mut self.autostart, "Run at startup");
                    ui.add_space(ROW_GAP);
                }
                // One error at a time, below the form: the invalid fields have a red border.
                // A space keeps the line height, so that the buttons below do not move.
                let status = error_text(&errors).unwrap_or_else(|| " ".to_string());
                ui.add(egui::Label::new(RichText::new(status).color(colors.0)).wrap_mode(egui::TextWrapMode::Extend));
                ui.add_space(ROW_GAP);
                ui.horizontal(|ui| {
                    if ui.link(RichText::new("Open logs folder").color(colors.1)).clicked() {
                        self.platform.open_folder(&log_dir());
                    }
                    ui.with_layout(egui::Layout::right_to_left(egui::Align::Center), |ui| {
                        if ui.button("Cancel").clicked() {
                            ctx.send_viewport_cmd(ViewportCommand::Close);
                        }
                        if ui.add_enabled(errors.is_empty(), Button::new("Save")).clicked() {
                            self.save_settings(&ctx);
                        }
                    });
                });
            },
        );

        if ctx.input(|input| input.key_pressed(Key::Enter)) {
            self.save_settings(&ctx);
        }
        if ctx.input(|input| input.key_pressed(Key::Escape)) {
            ctx.send_viewport_cmd(ViewportCommand::Close);
        }

        // Fit the window to its content
        let height = content.response.rect.height().ceil();
        if (height - self.height).abs() >= 1.0 {
            self.height = height;
            ctx.send_viewport_cmd(ViewportCommand::InnerSize(egui::vec2(WIDTH, height)));
        }
        if !self.ready {
            self.ready = true;
            tracing::info!("Settings dialog ready");
        }
    }
}

/// Show the dialog until closed, return true if the settings were saved.
pub fn run(platform: Arc<dyn Platform>, settings: Settings) -> bool {
    let theme_platform = platform.clone();
    let icon =
        icon_renderer(platform.icon_font(), move || theme_platform.apps_use_dark_theme()).render(None, &settings);
    let options = eframe::NativeOptions {
        viewport: ViewportBuilder::default()
            .with_title(TITLE)
            .with_inner_size([WIDTH, 400.0])
            .with_resizable(false)
            .with_maximize_button(false)
            .with_icon(IconData { rgba: icon.rgba, width: SIZE, height: SIZE }),
        centered: true,
        ..Default::default()
    };
    let saved = Arc::new(AtomicBool::new(false));
    let dialog_saved = saved.clone();
    let device_names = known_device_names(&settings, &seen_devices_file());
    let form = Form::new(settings, device_names);
    let result = eframe::run_native(
        TITLE,
        options,
        Box::new(move |creation| {
            // Follow the Windows app theme, elsewhere egui follows the system theme
            let dark = if cfg!(windows) {
                let dark = platform.apps_use_dark_theme();
                creation.egui_ctx.set_theme(if dark { Theme::Dark } else { Theme::Light });
                dark
            } else {
                creation.egui_ctx.system_theme() == Some(Theme::Dark)
            };
            let autostart = platform.is_autostart_enabled();
            Ok(Box::new(SettingsDialog {
                platform,
                form,
                autostart,
                saved: dialog_saved,
                dark,
                ready: false,
                height: 0.0,
            }))
        }),
    );
    if let Err(e) = result {
        tracing::error!("Could not open the settings dialog: {e}");
    }
    saved.load(Ordering::SeqCst)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn form() -> Form {
        Form::new(Settings::default(), vec!["Mouse".to_string(), "Headset".to_string()])
    }

    fn set(form: &mut Form, name: &str, value: &str) {
        let (_, text) = form.numbers.iter_mut().find(|(field, _)| field.name == name).unwrap();
        *text = value.to_string();
    }

    #[test]
    fn errors_are_shown_one_at_a_time_in_field_order() {
        for (name, value, expected) in [
            ("low_threshold", "100", "\u{26a0} Low battery (%): must be between 1 and 99"),
            ("check_interval_minutes", "abc", "\u{26a0} Check interval (minutes): must be a whole number"),
            ("critical_threshold", "30", "\u{26a0} Critical battery (%): must be below the low battery level"),
        ] {
            let mut form = form();
            set(&mut form, name, value);
            let (_, errors) = form.edited_settings();
            assert_eq!(error_text(&errors).as_deref(), Some(expected));
        }
    }

    #[test]
    fn unchecked_devices_are_disabled() {
        let mut form = form();
        form.devices[1].1 = false;
        set(&mut form, "low_threshold", " 30 ");
        let (settings, errors) = form.edited_settings();
        assert!(errors.is_empty());
        assert_eq!(settings.low_threshold, 30);
        assert_eq!(settings.disabled_devices, ["Headset".to_string()].into());
    }
}
