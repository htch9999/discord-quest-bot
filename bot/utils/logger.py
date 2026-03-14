"""
Per-user isolated logger with token masking filter.
"""

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler

from bot.config import LOG_DIR, DEBUG
from bot.utils.token_mask import mask_in_text


class TokenMaskFilter(logging.Filter):
    """Filter that masks tokens in log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_in_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: mask_in_text(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_in_text(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


def get_logger(name: str, user_id: str | None = None) -> logging.Logger:
    """
    Get a logger instance.
    If user_id is provided, logs go to a per-user file.
    """
    logger_name = f"quest_bot.{name}"
    if user_id:
        logger_name += f".{user_id}"

    logger = logging.getLogger(logger_name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    logger.addFilter(TokenMaskFilter())

    # Console handler
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if DEBUG else logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    console.setFormatter(fmt)
    logger.addHandler(console)

    # File handler
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    if user_id:
        log_file = log_dir / f"user_{user_id}.log"
    else:
        log_file = log_dir / f"{name}.log"

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger
