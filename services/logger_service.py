import logging
import os
from logging.handlers import TimedRotatingFileHandler
from config.settings import settings

os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("vicidial-listener")

if not logger.handlers:
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = TimedRotatingFileHandler(
        filename="logs/listener.log",
        when="midnight",      # Rotate every day at midnight
        interval=1,
        backupCount=30,       # Keep last 30 log files
        encoding="utf-8",
    )

    # Creates files like:
    # listener.log.2026-07-20
    file_handler.suffix = "%Y-%m-%d"

    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.propagate = False