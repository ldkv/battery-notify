"""
Settings dialog, generated from the `Settings` fields.
Runs in its own process: `battery-notifier settings`, exit code 0 when saved.
"""

import tkinter as tk
import tkinter.font as tkfont
from dataclasses import replace
from tkinter import ttk

import sv_ttk

from battery_notifier.configs import image_path
from battery_notifier.core.paths import log_dir
from battery_notifier.core.poller import known_device_names
from battery_notifier.core.settings import RANGE_ERROR, THRESHOLD_ERROR, Settings
from battery_notifier.logs import logger
from battery_notifier.platforms.base import Platform
from battery_notifier.ui.form import FieldKind, FormField, form_fields

PADDING = 20
ROW_GAP = 12
# Windows 11 "critical" text colors
ERROR_COLORS = {"light": "#c42b1c", "dark": "#ff99a4"}
CAPTION_COLORS = {"light": "#5d5d5d", "dark": "#a0a0a0"}
NOT_A_NUMBER = "Must be a whole number"


class SettingsDialog:
    def __init__(self, platform: Platform, settings: Settings):
        self.platform = platform
        self.settings = settings
        self.saved = False
        self.numbers: dict[str, tk.StringVar] = {}
        self.checklists: dict[str, dict[str, tk.BooleanVar]] = {}
        self.errors: dict[str, ttk.Label] = {}
        self.limits: dict[str, tuple[int | None, int | None]] = {}

        platform.enable_high_dpi()
        self.root = tk.Tk()
        self.root.title("Battery Notifier settings")
        self.root.resizable(False, False)
        self.root.iconphoto(True, tk.PhotoImage(file=image_path("battery-full.png")))
        theme = "dark" if platform.apps_use_dark_theme() else "light"
        sv_ttk.set_theme(theme)
        style = ttk.Style()
        style.configure("Error.TLabel", foreground=ERROR_COLORS[theme])
        style.configure("Caption.TLabel", foreground=CAPTION_COLORS[theme])

        frame = ttk.Frame(self.root, padding=PADDING)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        row = 0
        for form_field in form_fields():
            if form_field.kind is FieldKind.NUMBER:
                self.add_number(frame, row, form_field)
            else:
                self.add_checklist(frame, row, form_field)
            row += 1

        self.autostart = tk.BooleanVar(value=platform.is_autostart_enabled())
        if platform.supports_autostart:
            switch = ttk.Checkbutton(frame, text="Run at startup", variable=self.autostart, style="Switch.TCheckbutton")
            switch.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, ROW_GAP))
            row += 1

        self.link_font = tkfont.Font(font=style.lookup("TLabel", "font") or "TkDefaultFont", underline=True)
        logs_link = ttk.Label(
            frame, text="Open logs folder", style="Caption.TLabel", cursor="hand2", font=self.link_font
        )
        logs_link.bind("<Button-1>", lambda _: platform.open_folder(log_dir()))
        logs_link.grid(row=row, column=0, sticky="w", pady=(ROW_GAP, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=row, column=1, sticky="e", pady=(ROW_GAP, 0))
        self.save_button = ttk.Button(buttons, text="Save", style="Accent.TButton", command=self.save)
        self.save_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Cancel", command=self.root.destroy).grid(row=0, column=1)

        self.root.bind("<Return>", lambda _: self.save())
        self.root.bind("<Escape>", lambda _: self.root.destroy())
        self.fix_size()

    def add_number(self, frame: ttk.Frame, row: int, form_field: FormField):
        labels = ttk.Frame(frame)
        labels.grid(row=row, column=0, sticky="nw", padx=(0, PADDING), pady=(0, ROW_GAP))
        ttk.Label(labels, text=form_field.label).grid(sticky="w")
        if form_field.help_text:
            ttk.Label(labels, text=form_field.help_text, style="Caption.TLabel").grid(sticky="w")

        value = tk.StringVar(value=str(getattr(self.settings, form_field.name)))
        value.trace_add("write", lambda *_: self.refresh())
        self.numbers[form_field.name] = value
        widgets = ttk.Frame(frame)
        widgets.grid(row=row, column=1, sticky="ne", pady=(0, ROW_GAP))
        spinbox = ttk.Spinbox(widgets, from_=form_field.min or 0, to=form_field.max or 0, textvariable=value, width=6)
        spinbox.grid(sticky="e")
        self.errors[form_field.name] = ttk.Label(widgets, style="Error.TLabel")
        self.errors[form_field.name].grid(sticky="e")
        self.limits[form_field.name] = (form_field.min, form_field.max)

    def add_checklist(self, frame: ttk.Frame, row: int, form_field: FormField):
        group = ttk.LabelFrame(frame, text=form_field.label, padding=(PADDING // 2, 4))
        group.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, ROW_GAP))
        if form_field.help_text:
            ttk.Label(group, text=form_field.help_text, style="Caption.TLabel").grid(sticky="w", pady=(0, 4))

        disabled = getattr(self.settings, form_field.name)
        self.checklists[form_field.name] = {}
        for name in known_device_names(self.settings):
            enabled = tk.BooleanVar(value=name not in disabled)
            self.checklists[form_field.name][name] = enabled
            ttk.Checkbutton(group, text=name, variable=enabled).grid(sticky="w")

    def edited_settings(self) -> tuple[Settings, dict[str, str]]:
        """Settings as edited in the dialog, with an error message per invalid field."""
        values, errors = {}, {}
        for name, value in self.numbers.items():
            try:
                values[name] = int(value.get())
            except ValueError:
                errors[name] = NOT_A_NUMBER
        for name, checklist in self.checklists.items():
            values[name] = frozenset(device for device, enabled in checklist.items() if not enabled.get())

        edited = replace(self.settings, **{name: value for name, value in values.items() if name not in errors})
        return edited, edited.validate() | errors

    def refresh(self):
        _, errors = self.edited_settings()
        for name, label in self.errors.items():
            # A space keeps the line height, so that rows below do not move
            label.configure(text=errors.get(name, " "))
        self.save_button.state(["disabled"] if errors else ["!disabled"])

    def save(self):
        settings, errors = self.edited_settings()
        if errors:
            return
        settings.save()
        if self.platform.supports_autostart and self.autostart.get() != self.platform.is_autostart_enabled():
            self.platform.set_autostart(self.autostart.get())
        logger.info(f"Settings saved: {settings}")
        self.saved = True
        self.root.destroy()

    def fix_size(self):
        """Size and center the window for the longest error messages, so that showing one never resizes it."""
        for name, label in self.errors.items():
            low, high = self.limits[name]
            messages = [RANGE_ERROR.format(min=low, max=high), NOT_A_NUMBER, THRESHOLD_ERROR]
            label.configure(text=max(messages, key=len))
        self.root.update_idletasks()
        width, height = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        self.refresh()
        x = (self.root.winfo_screenwidth() - width) // 2
        y = (self.root.winfo_screenheight() - height) // 3
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def run(self) -> bool:
        """Show the dialog until closed, return True if the settings were saved."""
        self.root.after_idle(lambda: logger.info("Settings dialog ready"))
        self.root.mainloop()
        return self.saved
