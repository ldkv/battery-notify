import os
import tkinter as tk
from pathlib import Path

import pytest

from battery_notifier.core.settings import Settings
from battery_notifier.platforms.base import Platform
from battery_notifier.ui.settings_dialog import SettingsDialog


@pytest.fixture
def dialog():
    try:
        dialog = SettingsDialog(Platform(), Settings())
    except tk.TclError as e:
        pytest.skip(f"No display: {e}")
    dialog.root.update()
    yield dialog
    dialog.root.destroy()


def layout(dialog: SettingsDialog) -> list[tuple[int, int]]:
    """Window size and position of every field."""
    dialog.root.update()
    spinboxes = [(spinbox.winfo_x(), spinbox.winfo_y()) for spinbox in dialog.spinboxes.values()]
    return [(dialog.root.winfo_width(), dialog.root.winfo_height()), *spinboxes]


@pytest.mark.parametrize(
    "field, value, error",
    [
        ("low_threshold", "100", "\u26a0 Low battery (%): must be between 1 and 99"),
        ("check_interval_minutes", "abc", "\u26a0 Check interval (minutes): must be a whole number"),
        ("critical_threshold", "30", "\u26a0 Critical battery (%): must be below the low battery level"),
    ],
)
def test_errors_do_not_move_anything(dialog, field, value, error):
    before = layout(dialog)

    dialog.numbers[field].set(value)
    assert layout(dialog) == before
    assert dialog.status.cget("text") == error
    assert dialog.spinboxes[field].instate(["invalid"])
    assert dialog.save_button.instate(["disabled"])
    save_screenshot(dialog, f"error-{field}.png")

    dialog.numbers[field].set(str(getattr(Settings(), field)))
    assert layout(dialog) == before
    assert dialog.status.cget("text") == " "
    assert dialog.spinboxes[field].instate(["!invalid"])
    assert dialog.save_button.instate(["!disabled"])


def save_screenshot(dialog: SettingsDialog, name: str):
    """Save the dialog as shown, for review in CI artifacts, when DIALOG_SCREENSHOTS is set."""
    if not (folder := os.environ.get("DIALOG_SCREENSHOTS")):
        return
    from PIL import ImageGrab  # noqa: PLC0415

    root = dialog.root
    box = (
        root.winfo_rootx(),
        root.winfo_rooty(),
        root.winfo_rootx() + root.winfo_width(),
        root.winfo_rooty() + root.winfo_height(),
    )
    Path(folder).mkdir(exist_ok=True)
    ImageGrab.grab(box).save(Path(folder) / name)
