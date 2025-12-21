"""
Centralized logging configuration for the Arilo Processing Engine.
Supports JSON-structured logging for production and human-readable formatting with 'extra' fields for development.
"""

import logging
import logging.config
import os
import json
import uuid
from typing import Optional

try:
    from pythonjsonlogger import jsonlogger
except ImportError:
    jsonlogger = None

__all__ = ("configure_logging", "get_logger")


class ReadableExtraFormatter(logging.Formatter):
    """
    Custom formatter that appends 'extra' contextual data to the end of log lines.
    Useful for development where structured JSON is hard to read but data is needed.
    """

    def format(self, record):
        standard_attrs = (
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
        )
        extras = {k: v for k, v in record.__dict__.items() if k not in standard_attrs}

        line = super().format(record)

        if extras:
            extras = _json_safe(extras)
            line = f"{line} | {json.dumps(extras)}"
        return line


def _env() -> str:
    """Detect the current application environment."""
    return (os.getenv("APP_ENV") or os.getenv("ENV") or "development").lower()


def _level() -> str:
    """Detect the default logging level."""
    return (os.getenv("LOG_LEVEL") or "INFO").upper()


def _json_safe(obj):
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def configure_logging(
    env: Optional[str] = None, level: Optional[str] = None, force: bool = False
) -> None:
    """
    Initialize global logging configuration using dictConfig.

    Args:
        env (str, optional): Target environment ('production' enables JSON).
        level (str, optional): Logging level (DEBUG, INFO, etc.).
        force (bool): If True, reconfigures even if handlers exist.
    """
    env = (env or _env()).lower()
    level = (level or _level()).upper()

    root = logging.getLogger()
    if root.handlers and not force:
        return

    if env in ("production", "prod"):
        if jsonlogger:
            fmt = {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "fmt": "%(asctime)s %(name)s %(levelname)s %(message)s",
            }
            formatter_name = "json"
        else:
            fmt = {
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            }
            formatter_name = "plain"
    else:
        fmt = {
            "()": ReadableExtraFormatter,
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
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
    """
    Retrieve a named logger instance, ensuring logging is configured.
    Args:
        name (str, optional): Name for the logger, typically __name__.

    Returns:
        logging.Logger: Configured logger instance.
    """
    if not logging.getLogger().handlers:
        configure_logging()
    return logging.getLogger(name)
