import logging
import logging.config

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
                "filename": f"{GLOBAL_LOGGER_NAME}.log",
                "mode": "a",
                "maxBytes": 1024 * 1024 * 100,  # 100 MB
                "backupCount": 5,
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
