import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

# ── Log directory ─────────────────────────────────────────────────────────

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, f"mcp_{datetime.now().strftime('%Y%m%d')}.log")

# ── Formatter ─────────────────────────────────────────────────────────────

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

# ── Handlers ──────────────────────────────────────────────────────────────

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8"
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

# ── Root logger setup ─────────────────────────────────────────────────────

root_logger = logging.getLogger("selenium_mcp")
root_logger.setLevel(logging.DEBUG)

if not root_logger.handlers:
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a named child logger.
    Usage:
        from core.logger import get_logger
        log = get_logger(__name__)
    """
    return root_logger.getChild(name)
