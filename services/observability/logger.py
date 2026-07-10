"""
ICYQuant structured logger.
"""

from __future__ import annotations

import logging

from .context import (
    get_request_id,
    get_trace_id,
)


class ContextFilter(
    logging.Filter
):
    def filter(
        self,
        record,
    ) -> bool:
        record.context = {
            "request_id":
            get_request_id(),
            "trace_id":
            get_trace_id(),
        }
        return True


def create_logger(
    name: str,
) -> logging.Logger:
    logger = logging.getLogger(
        name
    )
    logger.setLevel(
        logging.INFO
    )

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.addFilter(
            ContextFilter()
        )
        logger.addHandler(
            handler
        )

    return logger