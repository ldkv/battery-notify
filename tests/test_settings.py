import pytest

from battery_notifier.core.settings import Settings


@pytest.fixture
def config_path(tmp_path):
    return tmp_path / "config.toml"


def test_missing_file_uses_defaults(config_path):
    assert Settings.load(config_path) == Settings()


def test_save_and_load_round_trip(config_path):
    settings = Settings(check_interval_minutes=5, low_threshold=30, disabled_devices=frozenset({"Mouse", "Headset"}))
    settings.save(config_path)

    assert Settings.load(config_path) == settings
    assert 'disabled_devices = [\n    "Headset",\n    "Mouse",\n]' in config_path.read_text()


def test_invalid_toml_uses_defaults(config_path):
    config_path.write_text("check_interval_minutes = ")
    assert Settings.load(config_path) == Settings()


@pytest.mark.parametrize(
    "content",
    [
        "check_interval_minutes = 0",  # below min
        "check_interval_minutes = '5'",  # wrong type
        "check_interval_minutes = true",  # bool is not an int
        "disabled_devices = 'Mouse'",  # not a list
    ],
)
def test_invalid_value_uses_its_default(config_path, content):
    config_path.write_text(f"low_threshold = 30\n{content}")
    assert Settings.load(config_path) == Settings(low_threshold=30)


def test_conflicting_thresholds_use_defaults(config_path):
    config_path.write_text("low_threshold = 15\ncritical_threshold = 15")
    assert Settings.load(config_path) == Settings(low_threshold=15)


def test_unknown_keys_are_ignored(config_path):
    config_path.write_text("theme = 'dark'\nlow_threshold = 30")
    assert Settings.load(config_path) == Settings(low_threshold=30)


def test_validate():
    assert Settings().validate() == {}
    assert Settings(low_threshold=60).validate() == {"low_threshold": "Must be between 5 and 50"}
    assert Settings(critical_threshold=20).validate() == {"critical_threshold": "Must be below the low battery level"}
