import os
import shutil
import sys
from pathlib import Path

from battery_notifier.core.paths import APP_NAME

# Keep in sync with --onefile-tempdir-spec in Taskfile.yml: each version unpacks to its own folder
UNPACK_ROOT = Path(os.environ.get("LOCALAPPDATA", "")) / APP_NAME / "app"


def is_frozen() -> bool:
    """True when running from the standalone executable built by Nuitka."""
    return "__compiled__" in globals()


def executable() -> str:
    """The standalone executable itself, not its unpacked copy in the cache."""
    return os.path.abspath(sys.argv[0])


def app_command(*args: str) -> list[str]:
    """Command line to start this app again, e.g. to open the settings dialog in its own process."""
    if is_frozen():
        return [executable(), *args]
    return [sys.executable, "-m", "battery_notifier", *args]


def app_environment() -> dict[str, str]:
    """
    Environment for app_command: without the variable telling the executable it was started by itself
    as the unpacked child, so that it starts as a fresh instance.
    """
    return {name: value for name, value in os.environ.items() if name != "NUITKA_ONEFILE_PARENT"}


def remove_old_versions(root: Path = UNPACK_ROOT, current: Path = Path(__file__)):
    """Delete the folders unpacked by previous versions, only if running from one of them."""
    current = current.resolve()
    if not is_frozen() or not current.is_relative_to(root.resolve()):
        return
    for folder in root.iterdir():
        if folder.is_dir() and not current.is_relative_to(folder.resolve()):
            shutil.rmtree(folder, ignore_errors=True)
