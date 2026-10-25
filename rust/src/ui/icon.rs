//! Tray icon: a battery glyph that follows the taskbar theme, amber when low and red when critical.
//! Uses the battery glyphs of the Windows icon font, or draws a battery where the font is missing.

use std::path::PathBuf;

use ab_glyph::{Font, FontVec, PxScale, ScaleFont, point};
use tiny_skia::{Color, FillRule, Paint, PathBuilder, Pixmap, Rect, Stroke, Transform};

use crate::core::policy::{BatteryStatus, battery_status};
use crate::core::settings::Settings;

pub const SIZE: u32 = 64;
/// The app icon, a battery in a gear, rendered from assets/icon/app-icon.svg by scripts/render_app_icon.py.
/// One PNG for both versions: it lives in the Python package, which must contain it.
pub const APP_ICON_PNG: &[u8] = include_bytes!("../../../src/battery_notifier/assets/app-icon.png");
const LOW_COLOR: Rgb = Rgb(0xff, 0xb9, 0x00); // Windows amber
const CRITICAL_COLOR: Rgb = Rgb(0xe8, 0x11, 0x23); // Windows red
const ON_DARK_COLOR: Rgb = Rgb(0xff, 0xff, 0xff);
const ON_LIGHT_COLOR: Rgb = Rgb(0x1c, 0x1c, 0x1c);
// Segoe Fluent Icons / Segoe MDL2 Assets: Battery0 to Battery9, Battery10 is out of sequence
const BATTERY_10_GLYPH: char = '\u{e83f}';
const UNKNOWN_GLYPH: char = '\u{e996}';

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rgb(pub u8, pub u8, pub u8);

/// Straight (not premultiplied) RGBA pixels, `SIZE` x `SIZE`.
pub struct IconImage {
    pub rgba: Vec<u8>,
}

impl IconImage {
    pub fn alpha(&self, x: u32, y: u32) -> u8 {
        self.rgba[((y * SIZE + x) * 4 + 3) as usize]
    }
}

pub trait IconRenderer: Send {
    /// Tray icon for the lowest battery level, None when no device reports one.
    fn render(&self, level: Option<u8>, settings: &Settings) -> IconImage;
}

pub fn battery_glyph(level: Option<u8>) -> char {
    let Some(level) = level else {
        return UNKNOWN_GLYPH;
    };
    // level / 10 rounded half to even, like Python's round()
    let (tens, units) = (u32::from(level.min(100)) / 10, u32::from(level.min(100)) % 10);
    let step = if units > 5 || (units == 5 && tens % 2 == 1) { tens + 1 } else { tens };
    match step {
        10 => BATTERY_10_GLYPH,
        step => char::from_u32(0xE850 + step).unwrap_or(UNKNOWN_GLYPH),
    }
}

pub fn icon_color(level: Option<u8>, settings: &Settings, dark_background: bool) -> Rgb {
    match battery_status(level, settings) {
        BatteryStatus::Low => LOW_COLOR,
        BatteryStatus::Critical => CRITICAL_COLOR,
        BatteryStatus::Normal if dark_background => ON_DARK_COLOR,
        BatteryStatus::Normal => ON_LIGHT_COLOR,
    }
}

type IsDarkBackground = Box<dyn Fn() -> bool + Send>;

struct GlyphIconRenderer {
    font: FontVec,
    is_dark_background: IsDarkBackground,
}

impl IconRenderer for GlyphIconRenderer {
    fn render(&self, level: Option<u8>, settings: &Settings) -> IconImage {
        let Rgb(red, green, blue) = icon_color(level, settings, (self.is_dark_background)());
        let mut rgba = vec![0; (SIZE * SIZE * 4) as usize];
        #[allow(clippy::cast_precision_loss)]
        let (size, scale) = (SIZE as f32, PxScale::from(SIZE as f32));
        let font = self.font.as_scaled(scale);
        let glyph_id = self.font.glyph_id(battery_glyph(level));
        // Centered on the advance width and between ascent and descent, like Pillow's "mm" anchor
        let x = (size - font.h_advance(glyph_id)) / 2.0;
        let baseline = (size + font.ascent() + font.descent()) / 2.0;
        if let Some(outline) = self.font.outline_glyph(glyph_id.with_scale_and_position(scale, point(x, baseline))) {
            let bounds = outline.px_bounds();
            outline.draw(|glyph_x, glyph_y, coverage| {
                #[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
                let (x, y) =
                    ((bounds.min.x as i32 + glyph_x.cast_signed()), (bounds.min.y as i32 + glyph_y.cast_signed()));
                if let (Ok(x @ 0..SIZE), Ok(y @ 0..SIZE)) = (u32::try_from(x), u32::try_from(y)) {
                    let pixel = ((y * SIZE + x) * 4) as usize;
                    #[allow(clippy::cast_possible_truncation, clippy::cast_sign_loss)]
                    let alpha = (coverage.clamp(0.0, 1.0) * 255.0).round() as u8;
                    rgba[pixel..pixel + 4].copy_from_slice(&[red, green, blue, alpha]);
                }
            });
        }
        IconImage { rgba }
    }
}

/// Fallback for OSes without the icon font: a horizontal battery, filled up to the level.
struct DrawnIconRenderer {
    is_dark_background: IsDarkBackground,
}

impl IconRenderer for DrawnIconRenderer {
    fn render(&self, level: Option<u8>, settings: &Settings) -> IconImage {
        let Rgb(red, green, blue) = icon_color(level, settings, (self.is_dark_background)());
        let mut pixmap = Pixmap::new(SIZE, SIZE).expect("non-zero icon size");
        let mut paint = Paint::default();
        paint.set_color(Color::from_rgba8(red, green, blue, 255));
        let (left, top, right, bottom, stroke) = (4.0, 18.0, 54.0, 46.0, 4.0);

        // Outline drawn inside the bounds, like Pillow
        let half = stroke / 2.0;
        if let Some(body) = rounded_rect(left + half, top + half, right - half, bottom - half, 6.0) {
            let stroke = Stroke { width: stroke, ..Stroke::default() };
            pixmap.stroke_path(&body, &paint, &stroke, Transform::identity(), None);
        }
        if let Some(terminal) = rounded_rect(right + 2.0, 26.0, right + 7.0, 38.0, 2.0) {
            pixmap.fill_path(&terminal, &paint, FillRule::Winding, Transform::identity(), None);
        }
        if let Some(level) = level.filter(|level| *level > 0) {
            let inner = right - left - 4.0 * stroke;
            let fill_right = left + 2.0 * stroke + inner * f32::from(level.min(100)) / 100.0;
            if let Some(fill) =
                Rect::from_ltrb(left + 2.0 * stroke, top + 2.0 * stroke, fill_right, bottom - 2.0 * stroke)
            {
                pixmap.fill_rect(fill, &paint, Transform::identity(), None);
            }
        }
        IconImage { rgba: pixmap.pixels().iter().flat_map(|pixel| straight_rgba(*pixel)).collect() }
    }
}

fn straight_rgba(pixel: tiny_skia::PremultipliedColorU8) -> [u8; 4] {
    let color = pixel.demultiply();
    [color.red(), color.green(), color.blue(), color.alpha()]
}

fn rounded_rect(left: f32, top: f32, right: f32, bottom: f32, radius: f32) -> Option<tiny_skia::Path> {
    let mut path = PathBuilder::new();
    path.move_to(left + radius, top);
    path.line_to(right - radius, top);
    path.quad_to(right, top, right, top + radius);
    path.line_to(right, bottom - radius);
    path.quad_to(right, bottom, right - radius, bottom);
    path.line_to(left + radius, bottom);
    path.quad_to(left, bottom, left, bottom - radius);
    path.line_to(left, top + radius);
    path.quad_to(left, top, left + radius, top);
    path.close();
    path.finish()
}

/// The glyph renderer when the icon font is available, else the drawn one.
pub fn icon_renderer(
    font_path: Option<PathBuf>,
    is_dark_background: impl Fn() -> bool + Send + 'static,
) -> Box<dyn IconRenderer> {
    let is_dark_background: IsDarkBackground = Box::new(is_dark_background);
    let font = font_path.and_then(|path| match std::fs::read(&path).map(FontVec::try_from_vec) {
        Ok(Ok(font)) => Some(font),
        error => {
            tracing::warn!("Could not load the icon font {}: {:?}", path.display(), error.err());
            None
        }
    });
    match font {
        Some(font) => Box::new(GlyphIconRenderer { font, is_dark_background }),
        None => Box::new(DrawnIconRenderer { is_dark_background }),
    }
}

/// The icon for `level` with default settings, as a PNG file.
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn glyphs() {
        for (level, code) in [
            (0, 0xE850),
            (4, 0xE850),
            (5, 0xE850),
            (6, 0xE851),
            (42, 0xE854),
            (90, 0xE859),
            (95, 0xE83F),
            (100, 0xE83F),
        ] {
            assert_eq!(battery_glyph(Some(level)), char::from_u32(code).unwrap(), "{level}");
        }
        assert_eq!(battery_glyph(None), UNKNOWN_GLYPH);
    }

    #[test]
    fn colors() {
        let settings = Settings { low_threshold: 20, critical_threshold: 10, ..Settings::default() };
        for (dark, theme_color) in [(true, ON_DARK_COLOR), (false, ON_LIGHT_COLOR)] {
            assert_eq!(icon_color(Some(80), &settings, dark), theme_color);
            assert_eq!(icon_color(None, &settings, dark), theme_color);
            assert_eq!(icon_color(Some(15), &settings, dark), LOW_COLOR);
            assert_eq!(icon_color(Some(5), &settings, dark), CRITICAL_COLOR);
        }
    }

    #[test]
    fn drawn_icon_fills_up_to_the_level() {
        let renderer = icon_renderer(None, || true);
        let (empty, full) =
            (renderer.render(Some(0), &Settings::default()), renderer.render(Some(100), &Settings::default()));

        let center = SIZE / 2;
        assert_eq!(empty.rgba.len(), (SIZE * SIZE * 4) as usize);
        assert_eq!(empty.alpha(center, center), 0); // transparent inside an empty battery
        assert_eq!(full.alpha(center, center), 255);
    }

    #[test]
    fn app_icon() {
        let icon = eframe::icon_data::from_png_bytes(APP_ICON_PNG).unwrap();
        assert_eq!((icon.width, icon.height), (256, 256));
    }
}
