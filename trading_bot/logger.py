"""Logging helpers.

The logger never writes credentials, tokens, or secrets. Only diagnostic
information about data retrieval, signals, and simulated trades is recorded.
"""

import logging
from pathlib import Path

from config import settings


def setup_logger(name: str = "trading_bot", level: int = logging.INFO) -> logging.Logger:
    """Return a configured logger that writes to logs/app.log and the console."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)

    log_path = Path(settings.LOG_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger