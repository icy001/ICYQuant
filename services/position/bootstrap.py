"""
Position module bootstrap.
"""

from __future__ import annotations

from .consumer import PositionConsumer


def register_position_handlers(
    trade_publisher,
    position_service,
):
    consumer = PositionConsumer(
        position_service
    )

    trade_publisher.subscribe(
        consumer.handle
    )

    return consumer