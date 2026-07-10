"""
Structured log formatter.
"""

from __future__ import annotations

import json

from datetime import datetime, timezone


class JsonFormatter:
    def format(
        self,
        record,
    ) -> str:
        payload = {
            "timestamp":
            datetime.now(
                timezone.utc
            )
            .isoformat(),
            "level":
            record.levelname,
            "message":
            record.getMessage(),
        }

        extra = getattr(
            record,
            "context",
            None,
        )

        if extra:
            payload.update(
                extra
            )

        return json.dumps(
            payload,
            ensure_ascii=False,
        )