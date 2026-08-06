"""Tracing Adapter — distributed tracing bridge for end-to-end workflow visibility."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class TracingAdapter:
    """Bridges workflow traces with the ICYQuant distributed tracing platform."""

    def __init__(self, *, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._started = False

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    def health_report(self) -> Dict[str, Any]:
        return {"started": self._started}
