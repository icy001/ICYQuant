"""Metrics Adapter — exports integration metrics to the platform metrics pipeline."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MetricsAdapter:
    """Exports integration-level metrics to the ICYQuant metrics platform."""

    def __init__(self, *, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._started = False

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    def health_report(self) -> Dict[str, Any]:
        return {"started": self._started}
