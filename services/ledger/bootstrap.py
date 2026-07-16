"""
Ledger bootstrap.
"""

from __future__ import annotations

from .consumer import LedgerConsumer


def register_ledger_handlers(
    trade_publisher,
    accounting_service,
):
    consumer = LedgerConsumer(
        accounting_service
    )

    trade_publisher.subscribe(
        consumer.handle
    )

    return consumer