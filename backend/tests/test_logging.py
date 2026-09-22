"""Logging configuration tests."""

from backend.app.core.logging import configure_logging


def test_logging_configuration_is_idempotent() -> None:
    logger = configure_logging("INFO")
    initial_handlers = tuple(logger.handlers)

    configured_again = configure_logging("DEBUG")

    assert configured_again is logger
    assert tuple(logger.handlers) == initial_handlers
    assert logger.level == 10
