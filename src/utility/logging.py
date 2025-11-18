import logging
import logging.config
import os
import sys
from typing import Optional

try:
    from pythonjsonlogger import jsonlogger  # type: ignore
except Exception:
    jsonlogger = None  # type: ignore

__all__ = ("configure_logging", "get_logger")


def _env() -> str:
    return (os.getenv("APP_ENV") or os.getenv("ENV") or "development").lower()


def _level() -> str:
    return (os.getenv("LOG_LEVEL") or "INFO").upper()


def configure_logging(env: Optional[str] = None, level: Optional[str] = None, force: bool = False) -> None:
    """
    Configure global logging.

    - env: "production"/"prod" enables JSON-style logs (if python-json-logger present),
           otherwise human-readable console logs are used.
    - level: standard logging level name (DEBUG, INFO, ...).
    - force: if True, reconfigure even if handlers already exist.
    """
    env = (env or _env()).lower()
    level = (level or _level()).upper()

    root = logging.getLogger()
    if root.handlers and not force:
        return

    if env in ("production", "prod"):
        if jsonlogger:
            fmt = {"()": "pythonjsonlogger.jsonlogger.JsonFormatter", "fmt": "%(asctime)s %(name)s %(levelname)s %(message)s"}
            formatter_name = "json"
        else:
            fmt = {"format": "%(asctime)s %(levelname)s [%(name)s] %(message)s", "datefmt": "%Y-%m-%dT%H:%M:%S"}
            formatter_name = "plain"
    else:
        fmt = {"format": "%(asctime)s %(levelname)s [%(name)s] %(message)s", "datefmt": "%Y-%m-%d %H:%M:%S"}
        formatter_name = "dev"

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {formatter_name: fmt},
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": formatter_name,
                "stream": "ext://sys.stdout",
                "level": level,
            }
        },
        "root": {"handlers": ["console"], "level": level},
    }

    logging.config.dictConfig(config)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a logger; ensure logging is configured with defaults on first use."""
    if not logging.getLogger().handlers:
        configure_logging()
    return logging.getLogger(name)