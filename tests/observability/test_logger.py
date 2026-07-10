import logging

from services.observability import (
    create_logger,
    create_context,
    set_context,
)


def test_create_logger():
    logger = create_logger("test")
    assert isinstance(logger, logging.Logger)


def test_logger_with_context():
    logger = create_logger("test")
    context = create_context()
    set_context(context)
    logger.info("test message")