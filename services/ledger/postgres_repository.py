"""
PostgreSQL ledger repository.
"""

from __future__ import annotations

import json

from datetime import datetime, timezone

from services.database.models import (
    LedgerEventModel,
)


class PostgreSQLLedgerRepository:
    def __init__(
        self,
        session,
    ):
        self.session = session

    def append(
        self,
        event,
    ):
        model = LedgerEventModel(
            id=str(
                event.id
            ),
            event_type=
            event.event_type.value,
            payload=json.dumps(
                event.payload
            ),
            created_at=datetime.now(
                timezone.utc
            )
        )
        self.session.add(
            model
        )
        self.session.commit()

    def count(
        self,
    ):
        return (
            self.session
            .query(
                LedgerEventModel
            )
            .count()
        )