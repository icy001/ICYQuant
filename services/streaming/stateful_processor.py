"""
Stateful Processor — event processor with persistent state management,
supporting checkpointed state for exactly-once fault-tolerant processing.

Commit 16 Part 1.4
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .stream_processor import (
    StreamProcessor,
    ProcessorConfig,
    ProcessorType,
    ProcessingResult,
)

logger = logging.getLogger(__name__)


class StatefulProcessor(StreamProcessor):
    """
    Event processor with persistent state management.

    Maintains state across events, supports checkpointing for
    fault recovery, and integrates with the exactly-once engine.

    State flow:
        Incoming Event → StateStore → Business Logic → Checkpoint

    Usage::

        class VWAPProcessor(StatefulProcessor):
            async def process(self, event):
                state = await self.get_state("vwap_accumulator")
                state["volume"] += event["volume"]
                state["cumulative_pv"] += event["price"] * event["volume"]
                state["vwap"] = state["cumulative_pv"] / state["volume"]
                await self.set_state("vwap_accumulator", state)
                return ProcessingResult(event_id=event["id"], output=state)
    """

    def __init__(
        self,
        config: Optional[ProcessorConfig] = None,
        state_store: Any = None,
    ) -> None:
        if config is None:
            config = ProcessorConfig(processor_type=ProcessorType.STATEFUL)
        else:
            config.processor_type = ProcessorType.STATEFUL

        super().__init__(config)
        self._state_store = state_store
        self._local_state: dict[str, Any] = {}
        self._checkpoint_counter = 0

    async def initialize(self) -> None:
        """Initialize with state store."""
        await super().initialize()
        if self._state_store:
            logger.info("StatefulProcessor using external state store.")
        logger.info("StatefulProcessor initialized.")

    async def stop(self) -> None:
        """Stop and flush state."""
        if self._state_store:
            for key, value in self._local_state.items():
                await self._state_store.put(key, value)
            self._local_state.clear()
        await super().stop()

    async def get_state(self, key: str, default: Any = None) -> Any:
        """Get a state value by key."""
        if key in self._local_state:
            return self._local_state[key]

        if self._state_store:
            value = await self._state_store.get(key)
            if value is not None:
                self._local_state[key] = value
                return value

        return default

    async def set_state(self, key: str, value: Any) -> None:
        """Set a state value."""
        self._local_state[key] = value
        if self._state_store:
            await self._state_store.put(key, value)

    async def delete_state(self, key: str) -> bool:
        """Delete a state value."""
        self._local_state.pop(key, None)
        if self._state_store:
            return await self._state_store.delete(key)
        return True

    async def clear_state(self) -> None:
        """Clear all local and remote state."""
        self._local_state.clear()
        if self._state_store:
            await self._state_store.clear()

    async def snapshot_state(self) -> dict[str, Any]:
        """Take a snapshot of current state."""
        return dict(self._local_state)

    async def restore_state(self, snapshot: dict[str, Any]) -> None:
        """Restore state from a snapshot."""
        self._local_state = dict(snapshot)
        if self._state_store:
            for key, value in snapshot.items():
                await self._state_store.put(key, value)

    async def process(self, event: Any) -> ProcessingResult:
        """Override in subclass to implement business logic."""
        raise NotImplementedError("Subclass must implement process()")

    async def stats(self) -> dict[str, Any]:
        """Get processor statistics including state info."""
        base = await super().stats()
        base["state_keys"] = len(self._local_state)
        base["has_external_store"] = self._state_store is not None
        return base
