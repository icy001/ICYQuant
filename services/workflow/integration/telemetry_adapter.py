"""Telemetry Adapter — unified telemetry bridge for integration observability."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TelemetryAdapter:
    """Bridges integration telemetry with the platform telemetry pipeline."""

    def __init__(self, *, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._started = False

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    def health_report(self) -> Dict[str, Any]:
        return {"started": self._started}
