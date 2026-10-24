import pytest

from battery_notifier import launcher
from battery_notifier.launcher import app_environment, remove_old_versions


@pytest.fixture
def frozen(monkeypatch):
    monkeypatch.setattr(launcher, "is_frozen", lambda: True)


@pytest.fixture
def unpacked(tmp_path):
    """Folders unpacked by 3 versions, the app running from the current one."""
    root = tmp_path / "app"
    for version in ("0.2.0.0", "0.2.1.0", "0.3.0.0"):
        (root / version / "battery_notifier").mkdir(parents=True)
    current = root / "0.3.0.0" / "battery_notifier" / "launcher.py"
    current.touch()
    return root, current


def test_remove_old_versions(frozen, unpacked):
    root, current = unpacked
    remove_old_versions(root, current)
    assert [folder.name for folder in root.iterdir()] == ["0.3.0.0"]


def test_keep_everything_when_not_running_from_the_unpack_folder(frozen, unpacked, tmp_path):
    root, _ = unpacked
    remove_old_versions(root, tmp_path / "elsewhere" / "launcher.py")
    assert len(list(root.iterdir())) == 3  # noqa: PLR2004


def test_keep_everything_when_running_from_source(unpacked):
    root, current = unpacked
    remove_old_versions(root, current)
    assert len(list(root.iterdir())) == 3  # noqa: PLR2004


def test_app_environment_drops_onefile_parent(monkeypatch):
    monkeypatch.setenv("NUITKA_ONEFILE_PARENT", "1234")
    monkeypatch.setenv("KEEP_ME", "1")
    env = app_environment()
    assert "NUITKA_ONEFILE_PARENT" not in env
    assert env["KEEP_ME"] == "1"
