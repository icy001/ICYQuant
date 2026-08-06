"""Runtime Manager — manages the lifecycle of active workflow instances.

The :class:`RuntimeManager` tracks all active workflow instances and their
lifecycle transitions (start → run → pause → resume → stop).
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from .runtime_state import RuntimeState

logger = logging.getLogger(__name__)


class RuntimeManager:
    """Manages active workflow runtime instances and their lifecycle."""

    def __init__(self) -> None:
        self._state = RuntimeState.UNINITIALIZED
        self._lock = threading.RLock()
        self._instances: Dict[str, Dict[str, Any]] = {}
        self._started_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        with self._lock:
            self._state = RuntimeState.INITIALIZING
            self._started_at = datetime.utcnow()
        logger.info("RuntimeManager: started")
        with self._lock:
            self._state = RuntimeState.READY

    async def shutdown(self) -> None:
        with self._lock:
            self._state = RuntimeState.STOPPING
        logger.info("RuntimeManager: shutting down (%d active instances)", len(self._instances))
        self._instances.clear()
        with self._lock:
            self._state = RuntimeState.STOPPED
        logger.info("RuntimeManager: stopped")

    # ------------------------------------------------------------------
    # Instance management
    # ------------------------------------------------------------------

    def register_instance(self, execution_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Register an active workflow instance."""
        with self._lock:
            self._instances[execution_id] = {
                "execution_id": execution_id,
                "registered_at": datetime.utcnow(),
                "metadata": metadata or {},
            }
        logger.debug("RuntimeManager: registered instance %s", execution_id)

    def unregister_instance(self, execution_id: str) -> None:
        """Remove a completed/failed workflow instance."""
        with self._lock:
            self._instances.pop(execution_id, None)
        logger.debug("RuntimeManager: unregistered instance %s", execution_id)

    def get_instance(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Return metadata for a registered instance."""
        with self._lock:
            return self._instances.get(execution_id)

    def list_instances(self) -> List[str]:
        """Return execution ids of all active instances."""
        with self._lock:
            return list(self._instances.keys())

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._instances)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "state": self._state.value,
                "active_instances": len(self._instances),
                "started_at": self._started_at.isoformat() if self._started_at else None,
            }
