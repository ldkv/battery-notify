import tkinter as tk

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


def window_size(dialog: SettingsDialog) -> tuple[int, int]:
    dialog.root.update()
    return dialog.root.winfo_width(), dialog.root.winfo_height()


@pytest.mark.parametrize(
    "field, value, error",
    [
        ("low_threshold", "100", "Must be between 1 and 99"),
        ("check_interval_minutes", "abc", "Must be a whole number"),
        ("critical_threshold", "30", "Must be below the low battery level"),
    ],
)
def test_error_messages_do_not_resize_the_window(dialog, field, value, error):
    size = window_size(dialog)

    dialog.numbers[field].set(value)
    assert window_size(dialog) == size
    assert dialog.errors[field].cget("text") == error
    assert dialog.save_button.instate(["disabled"])

    dialog.numbers[field].set(str(getattr(Settings(), field)))
    assert window_size(dialog) == size
    assert dialog.save_button.instate(["!disabled"])
