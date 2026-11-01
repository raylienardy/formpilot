"""Logging setup for FormPilot.

Provides dual logging: console (INFO level) and file (DEBUG level).
The log file location is configurable but defaults to ./logs/formpilot.log.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

DEFAULT_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    name: str = "formpilot",
    level: str = "INFO",
    log_file: str | Path | None = "./logs/formpilot.log",
) -> logging.Logger:
    """Set up a logger with console and optional file handlers.

    Args:
        name: Logger name (default: "formpilot").
        level: Console log level (default: "INFO").
        log_file: Path to log file. If None, no file handler is added.
            Directory will be created if it doesn't exist.

    Returns:
        Configured logger instance.

    Example:
        >>> logger = setup_logger("formpilot.scraper", "DEBUG")
        >>> logger.info("Opening form...")
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # master level; handlers filter

    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    formatter = logging.Formatter(DEFAULT_LOG_FORMAT, datefmt=DEFAULT_DATE_FORMAT)

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file is not None:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "formpilot") -> logging.Logger:
    """Get a logger by name without re-configuring.

    Use this in modules after setup_logger() has been called once
    at the entry point.

    Args:
        name: Logger name (default: "formpilot").

    Returns:
        Logger instance (may be unconfigured if setup_logger not called).
    """
    return logging.getLogger(name)
