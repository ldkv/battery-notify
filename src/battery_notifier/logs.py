import logging
import logging.config

from battery_notifier.core.paths import log_dir

GLOBAL_LOGGER_NAME = "battery_notifier"


def configure_logging():
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": "[{asctime}: {levelname}/{threadName}][{filename:s}:L{lineno}] {message}",
                "style": "{",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "simple",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "simple",
                "filename": log_dir() / f"{GLOBAL_LOGGER_NAME}.log",
                "mode": "a",
                "maxBytes": 1024 * 1024 * 10,  # 10 MB
                "backupCount": 3,
            },
        },
        "loggers": {
            GLOBAL_LOGGER_NAME: {
                "handlers": ["console", "file"],
                "level": "INFO",
            },
        },
    }
    logging.config.dictConfig(logging_config)


logger = logging.getLogger(GLOBAL_LOGGER_NAME)
