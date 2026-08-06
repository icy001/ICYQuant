"""Configuration Adapter — dynamic workflow configuration with hot reload.

Supports:

* **Workflow Parameters** — default inputs, timeouts, retry policies
* **Hot Reload** — configuration changes applied without restart
* **Runtime Refresh** — running workflows pick up changes

Architecture::

    Workflow Configuration → Hot Reload → Runtime Refresh
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkflowConfig:
    """Configuration for a single workflow."""

    workflow_id: str
    timeout_seconds: float = 300.0
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    concurrency_limit: int = 10
    priority: int = 50
    parameters: Dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "concurrency_limit": self.concurrency_limit,
            "priority": self.priority,
            "parameters": dict(self.parameters),
            "version": self.version,
        }


class ConfigurationAdapter:
    """Dynamic workflow configuration with hot reload support.

    Usage::

        adapter = ConfigurationAdapter()
        await adapter.start()
        cfg = adapter.get_config("order_execution")
        adapter.on_change(my_handler)
    """

    def __init__(self, *, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._lock = threading.RLock()
        self._started = False
        self._configs: Dict[str, WorkflowConfig] = {}
        self._on_change_callbacks: list = []

        # Watch task
        self._watch_task: Optional[asyncio.Task] = None
        self._watch_interval = float(self._config.get("watch_interval", 10.0))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._started = True
        self._watch_task = asyncio.create_task(self._watch_loop())
        logger.info("ConfigurationAdapter: started")

    async def stop(self) -> None:
        self._started = False
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
        logger.info("ConfigurationAdapter: stopped")

    # ------------------------------------------------------------------
    # Config management
    # ------------------------------------------------------------------

    async def set_config(self, workflow_id: str, config: WorkflowConfig) -> None:
        """Set or update configuration for a workflow."""
        with self._lock:
            old = self._configs.get(workflow_id)
            config.version = (old.version + 1) if old else 1
            config.updated_at = datetime.utcnow()
            self._configs[workflow_id] = config

        for cb in self._on_change_callbacks:
            try:
                cb(workflow_id, config)
            except Exception:
                logger.exception("ConfigurationAdapter: change callback error")

        logger.debug("ConfigurationAdapter: config set for %s (v%d)", workflow_id, config.version)

    def get_config(self, workflow_id: str) -> Optional[WorkflowConfig]:
        with self._lock:
            return self._configs.get(workflow_id)

    async def list_configs(self) -> List[WorkflowConfig]:
        with self._lock:
            return list(self._configs.values())

    async def delete_config(self, workflow_id: str) -> bool:
        with self._lock:
            return self._configs.pop(workflow_id, None) is not None

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------

    async def set_defaults(
        self,
        *,
        timeout_seconds: float = 300.0,
        max_retries: int = 3,
        concurrency_limit: int = 10,
    ) -> None:
        """Set global defaults applied when no per-workflow config exists."""
        self._default_timeout = timeout_seconds
        self._default_retries = max_retries
        self._default_concurrency = concurrency_limit

    async def get_effective_config(self, workflow_id: str) -> WorkflowConfig:
        """Get config with defaults applied."""
        cfg = self.get_config(workflow_id)
        if cfg:
            return cfg
        return WorkflowConfig(
            workflow_id=workflow_id,
            timeout_seconds=self._config.get("default_timeout", 300.0),
            max_retries=self._config.get("default_max_retries", 3),
            concurrency_limit=self._config.get("default_concurrency_limit", 10),
        )

    # ------------------------------------------------------------------
    # Change notification
    # ------------------------------------------------------------------

    def on_change(self, callback) -> None:
        self._on_change_callbacks.append(callback)

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    async def sync(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_configs": len(self._configs),
                "workflows": list(self._configs.keys()),
            }

    async def _watch_loop(self) -> None:
        while self._started:
            try:
                await asyncio.sleep(self._watch_interval)
                # In production: pull from config center / etcd
            except asyncio.CancelledError:
                break

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "total_configs": len(self._configs),
                "watch_interval_seconds": self._watch_interval,
            }
