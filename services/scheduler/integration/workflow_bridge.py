"""Workflow Bridge — bidirectional bridge between Scheduler and Workflow Engine.

The :class:`WorkflowBridge` provides a bidirectional communication channel
between the Distributed Scheduler and the Workflow Engine. It handles:

* Scheduler → Workflow: trigger dispatch, lifecycle commands
* Workflow → Scheduler: status updates, completion callbacks, retry requests

Architecture::

    SchedulerEngine ←──→ WorkflowBridge ←──→ WorkflowEngine
         │                     │                    │
    Trigger dispatch    State sync          Execution runtime
"""

from __future__ import annotations

import asyncio
import enum
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class BridgeState(enum.Enum):
    """Workflow bridge connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    PARTIALLY_CONNECTED = "partially_connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


class WorkflowBridge:
    """Bidirectional bridge between scheduler and workflow engine.

    Responsibilities:
    * Forward scheduler triggers to workflow engine
    * Relay workflow status back to scheduler
    * Handle retry and backoff for transient failures
    * Buffer messages during disconnection

    Usage::

        bridge = WorkflowBridge(
            scheduler_engine=engine,
            workflow_adapter=adapter,
        )
        await bridge.connect()
        await bridge.forward_trigger(trigger_context)
    """

    def __init__(
        self,
        scheduler_engine: Any = None,
        workflow_adapter: Any = None,
    ) -> None:
        self._scheduler = scheduler_engine
        self._adapter = workflow_adapter
        self._state = BridgeState.DISCONNECTED
        self._lock = threading.Lock()
        self._message_buffer: List[Dict[str, Any]] = []
        self._max_buffer_size = 10000
        self._callbacks: Dict[str, List[Callable]] = {
            "on_completed": [],
            "on_failed": [],
            "on_retry": [],
            "on_timeout": [],
        }
        self._forward_count: int = 0
        self._relay_count: int = 0
        self._buffer_dropped: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> BridgeState:
        return self._state

    @property
    def buffer_size(self) -> int:
        return len(self._message_buffer)

    @property
    def forward_count(self) -> int:
        return self._forward_count

    @property
    def relay_count(self) -> int:
        return self._relay_count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Establish the bridge connection."""
        self._set_state(BridgeState.CONNECTING)
        logger.info("WorkflowBridge: connecting")

        scheduler_ok = self._scheduler is not None
        adapter_ok = self._adapter is not None

        if scheduler_ok and adapter_ok:
            self._set_state(BridgeState.CONNECTED)
        elif scheduler_ok or adapter_ok:
            self._set_state(BridgeState.PARTIALLY_CONNECTED)
        else:
            self._set_state(BridgeState.ERROR)
            raise RuntimeError("WorkflowBridge: both scheduler and adapter are None")

        # Flush buffered messages
        await self._flush_buffer()
        logger.info("WorkflowBridge: connected")

    async def disconnect(self) -> None:
        """Tear down the bridge connection."""
        self._set_state(BridgeState.DISCONNECTING)
        await self._flush_buffer()
        self._set_state(BridgeState.DISCONNECTED)
        logger.info("WorkflowBridge: disconnected")

    async def synchronize(self) -> Dict[str, Any]:
        """Synchronize bridge state."""
        return {
            "state": self._state.value,
            "buffer_size": len(self._message_buffer),
            "forward_count": self._forward_count,
            "relay_count": self._relay_count,
        }

    # ------------------------------------------------------------------
    # Forward (Scheduler → Workflow)
    # ------------------------------------------------------------------

    async def forward_trigger(self, trigger_context: Dict[str, Any]) -> Dict[str, Any]:
        """Forward a scheduler trigger to the workflow engine.

        If the bridge is disconnected, the message is buffered for later delivery.
        """
        self._forward_count += 1

        if self._state != BridgeState.CONNECTED:
            # Buffer for later delivery
            if len(self._message_buffer) < self._max_buffer_size:
                self._message_buffer.append({
                    "type": "trigger",
                    "context": trigger_context,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                return {"status": "buffered", "buffer_size": len(self._message_buffer)}
            else:
                self._buffer_dropped += 1
                return {"status": "dropped", "reason": "buffer_full"}

        # Forward immediately
        if self._adapter:
            return await self._adapter.launch(trigger_context)
        return {"status": "no_adapter"}

    async def forward_command(self, command: str, workflow_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Forward a lifecycle command to a running workflow."""
        if not self._adapter:
            return {"status": "no_adapter"}

        command_map = {
            "cancel": self._adapter.cancel,
            "pause": self._adapter.pause,
            "resume": self._adapter.resume,
            "recover": self._adapter.recover,
        }

        handler = command_map.get(command)
        if handler:
            return await handler(workflow_id)
        return {"status": "unknown_command", "command": command}

    # ------------------------------------------------------------------
    # Relay (Workflow → Scheduler)
    # ------------------------------------------------------------------

    async def relay_status(self, workflow_id: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Relay a workflow status update back to the scheduler."""
        self._relay_count += 1
        logger.debug("WorkflowBridge: relay status for %s: %s", workflow_id, status)

        # Invoke callbacks
        if status == "completed":
            for cb in self._callbacks["on_completed"]:
                await self._invoke_callback(cb, workflow_id, details)
        elif status == "failed":
            for cb in self._callbacks["on_failed"]:
                await self._invoke_callback(cb, workflow_id, details)
        elif status == "retrying":
            for cb in self._callbacks["on_retry"]:
                await self._invoke_callback(cb, workflow_id, details)
        elif status == "timeout":
            for cb in self._callbacks["on_timeout"]:
                await self._invoke_callback(cb, workflow_id, details)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_completed(self, callback: Callable) -> None:
        """Register a callback for workflow completion."""
        self._callbacks["on_completed"].append(callback)

    def on_failed(self, callback: Callable) -> None:
        """Register a callback for workflow failure."""
        self._callbacks["on_failed"].append(callback)

    def on_retry(self, callback: Callable) -> None:
        """Register a callback for workflow retry."""
        self._callbacks["on_retry"].append(callback)

    def on_timeout(self, callback: Callable) -> None:
        """Register a callback for workflow timeout."""
        self._callbacks["on_timeout"].append(callback)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _flush_buffer(self) -> None:
        """Flush buffered messages when connection is restored."""
        if not self._message_buffer:
            return
        logger.info("WorkflowBridge: flushing %d buffered messages", len(self._message_buffer))
        messages = self._message_buffer[:]
        self._message_buffer.clear()

        for msg in messages:
            try:
                if msg["type"] == "trigger":
                    await self.forward_trigger(msg["context"])
            except Exception as exc:
                logger.warning("WorkflowBridge: flush error: %s", exc)

    async def _invoke_callback(self, callback: Callable, *args: Any) -> None:
        """Safely invoke a callback."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as exc:
            logger.warning("WorkflowBridge: callback error: %s", exc)

    def _set_state(self, state: BridgeState) -> None:
        with self._lock:
            self._state = state
