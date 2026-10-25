import subprocess
import sys
import time
import tkinter as tk

import pytest

STARTUP_S = 4
CLOSE_TIMEOUT_S = 15


@pytest.fixture(autouse=True)
def display():
    try:
        tk.Tk().destroy()
    except tk.TclError as e:
        pytest.skip(f"No display: {e}")


def test_dialog_closes_when_the_tray_quits():
    """The tray holds the other end of the dialog's stdin: closing it is the tray quitting."""
    command = [sys.executable, "-m", "battery_notifier", "settings", "--close-with-tray"]
    dialog = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        time.sleep(STARTUP_S)
        assert dialog.poll() is None, "the dialog must stay open while the tray runs"
        assert dialog.stdin is not None
        dialog.stdin.close()
        assert dialog.wait(timeout=CLOSE_TIMEOUT_S) == 1  # closed without saving
    finally:
        dialog.kill()
