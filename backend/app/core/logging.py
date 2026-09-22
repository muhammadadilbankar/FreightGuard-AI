"""Small, idempotent logging configuration for FreightGuard modules."""

import logging

LOGGER_NAME = "freightguard"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def configure_logging(level: str) -> logging.Logger:
    """Configure and return the application logger without duplicate handlers."""
    logger = logging.getLogger(LOGGER_NAME)
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    logger.propagate = False

    handler = next(
        (item for item in logger.handlers if getattr(item, "_freightguard", False)),
        None,
    )
    if handler is None:
        handler = logging.StreamHandler()
        handler._freightguard = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    handler.setLevel(numeric_level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    return logger
