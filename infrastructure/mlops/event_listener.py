"""
MLOps Event Listener — event-driven pipeline triggers.

Listens for system events (data updates, model registry changes,
drift alerts, etc.) and triggers appropriate MLOps pipeline actions.
"""

import enum
import time
import uuid
import threading
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class EventType(str, enum.Enum):
    """Types of MLOps events."""
    DATA_UPDATED = "data_updated"
    MODEL_REGISTERED = "model_registered"
    MODEL_PROMOTED = "model_promoted"
    MODEL_DEMOTED = "model_demoted"
    DRIFT_DETECTED = "drift_detected"
    PERFORMANCE_DEGRADED = "performance_degraded"
    TRAINING_COMPLETED = "training_completed"
    TRAINING_FAILED = "training_failed"
    EVALUATION_COMPLETED = "evaluation_completed"
    DEPLOYMENT_COMPLETED = "deployment_completed"
    DEPLOYMENT_ROLLED_BACK = "deployment_rolled_back"
    CHALLENGER_PROMOTED = "challenger_promoted"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    SYSTEM_ALERT = "system_alert"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class MLOpsEvent:
    """An event in the MLOps system."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    event_type: EventType = EventType.SYSTEM_ALERT
    source: str = ""
    model_name: str = ""
    model_version: str = ""

    # Payload
    data: Dict[str, Any] = field(default_factory=dict)

    # Timing
    timestamp: float = field(default_factory=time.time)

    # Priority
    priority: int = 0  # 0=normal, 1=high, 2=critical

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "data": self.data,
            "timestamp": self.timestamp,
            "priority": self.priority,
        }


@dataclass
class EventConfig:
    """Configuration for the event listener."""

    # Queue
    max_queue_size: int = 10000
    worker_count: int = 4

    # Filtering
    enabled_event_types: Optional[List[EventType]] = None  # None = all enabled

    # Processing
    batch_size: int = 10
    poll_interval_seconds: float = 0.1

    # Dead letter
    max_retries: int = 3
    dead_letter_enabled: bool = True


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------

class EventBus:
    """Simple in-process event bus for MLOps events.

    Supports publish/subscribe pattern with filtering by event type.
    """

    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {
            et: [] for et in EventType
        }
        self._wildcard_subscribers: List[Callable] = []
        self._event_history: List[MLOpsEvent] = []
        self._max_history: int = 1000

    def publish(self, event: MLOpsEvent) -> None:
        """Publish an event to all subscribers."""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        # Notify type-specific subscribers
        for callback in self._subscribers.get(event.event_type, []):
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event subscriber error ({event.event_type}): {e}")

        # Notify wildcard subscribers
        for callback in self._wildcard_subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Wildcard subscriber error: {e}")

    def subscribe(
        self, event_type: Optional[EventType], callback: Callable
    ) -> None:
        """Subscribe to events.

        Args:
            event_type: Specific event type or None for all events.
            callback: Function to call with MLOpsEvent.
        """
        if event_type is None:
            self._wildcard_subscribers.append(callback)
        else:
            self._subscribers[event_type].append(callback)

    def unsubscribe(
        self, event_type: Optional[EventType], callback: Callable
    ) -> None:
        """Unsubscribe from events."""
        if event_type is None:
            if callback in self._wildcard_subscribers:
                self._wildcard_subscribers.remove(callback)
        else:
            subs = self._subscribers.get(event_type, [])
            if callback in subs:
                subs.remove(callback)

    def get_history(
        self, event_type: Optional[EventType] = None, limit: int = 50
    ) -> List[MLOpsEvent]:
        """Get recent event history."""
        events = self._event_history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    def reset(self) -> None:
        """Reset event bus."""
        self._subscribers = {et: [] for et in EventType}
        self._wildcard_subscribers.clear()
        self._event_history.clear()


# ---------------------------------------------------------------------------
# Event Listener
# ---------------------------------------------------------------------------

class EventListener:
    """Listens for MLOps events and triggers pipeline actions.

    Bridges external events (data updates, model changes) with
    MLOps pipeline actions (retraining, evaluation, deployment).

    Usage::

        listener = EventListener(config, event_bus)
        listener.on(EventType.DATA_UPDATED, lambda e: trainer.train(e.model_name))
        listener.on(EventType.DRIFT_DETECTED, lambda e: trainer.train(e.model_name))
        listener.start()
    """

    def __init__(self, config: EventConfig, event_bus: Optional[EventBus] = None):
        self.config = config
        self.event_bus = event_bus or EventBus()
        self._handlers: Dict[EventType, List[Callable]] = {
            et: [] for et in EventType
        }
        self._queue: List[MLOpsEvent] = []
        self._dead_letter: List[MLOpsEvent] = []
        self._running = False
        self._workers: List[threading.Thread] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Handler Registration
    # ------------------------------------------------------------------

    def on(self, event_type: EventType, handler: Callable) -> None:
        """Register a handler for a specific event type.

        Args:
            event_type: Type of event to handle.
            handler: Function that receives an MLOpsEvent.
        """
        self._handlers[event_type].append(handler)

    def off(self, event_type: EventType, handler: Callable) -> None:
        """Remove a handler for an event type."""
        if handler in self._handlers.get(event_type, []):
            self._handlers[event_type].remove(handler)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the event listener workers."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()

        for i in range(self.config.worker_count):
            worker = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name=f"mlops-event-worker-{i}",
            )
            worker.start()
            self._workers.append(worker)

        logger.info(f"EventListener started with {self.config.worker_count} workers")

    def stop(self) -> None:
        """Stop the event listener."""
        self._stop_event.set()
        for worker in self._workers:
            worker.join(timeout=5.0)
        self._workers.clear()
        self._running = False
        logger.info("EventListener stopped")

    def emit(self, event: MLOpsEvent) -> None:
        """Emit an event to be processed.

        Args:
            event: The MLOps event to process.
        """
        with self._lock:
            if len(self._queue) >= self.config.max_queue_size:
                logger.warning(f"Event queue full ({self.config.max_queue_size}), dropping event")
                return
            self._queue.append(event)

        # Also publish to event bus
        self.event_bus.publish(event)

    # ------------------------------------------------------------------
    # Worker Loop
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """Worker thread that processes events from the queue."""
        while not self._stop_event.is_set():
            event: Optional[MLOpsEvent] = None

            with self._lock:
                if self._queue:
                    event = self._queue.pop(0)

            if event:
                self._process_event(event)
            else:
                self._stop_event.wait(timeout=self.config.poll_interval_seconds)

    def _process_event(self, event: MLOpsEvent) -> None:
        """Process a single event through registered handlers."""
        # Check if event type is enabled
        if (
            self.config.enabled_event_types is not None
            and event.event_type not in self.config.enabled_event_types
        ):
            return

        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            return

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"Handler error for {event.event_type.value}: {e}"
                )
                # Dead letter
                if self.config.dead_letter_enabled:
                    self._dead_letter.append(event)

    # ------------------------------------------------------------------
    # Convenience Emitters
    # ------------------------------------------------------------------

    def emit_data_updated(self, source: str, model_name: str, **kwargs) -> None:
        """Emit a data_updated event."""
        self.emit(MLOpsEvent(
            event_type=EventType.DATA_UPDATED,
            source=source,
            model_name=model_name,
            data=kwargs,
        ))

    def emit_model_registered(
        self, model_name: str, model_version: str, **kwargs
    ) -> None:
        """Emit a model_registered event."""
        self.emit(MLOpsEvent(
            event_type=EventType.MODEL_REGISTERED,
            source="model_registry",
            model_name=model_name,
            model_version=model_version,
            data=kwargs,
        ))

    def emit_drift_detected(
        self, model_name: str, drift_type: str, severity: str, **kwargs
    ) -> None:
        """Emit a drift_detected event."""
        self.emit(MLOpsEvent(
            event_type=EventType.DRIFT_DETECTED,
            source="drift_detector",
            model_name=model_name,
            data={"drift_type": drift_type, "severity": severity, **kwargs},
            priority=1,
        ))

    def emit_training_completed(
        self, model_name: str, model_version: str, metrics: Dict[str, float]
    ) -> None:
        """Emit a training_completed event."""
        self.emit(MLOpsEvent(
            event_type=EventType.TRAINING_COMPLETED,
            source="trainer",
            model_name=model_name,
            model_version=model_version,
            data={"metrics": metrics},
        ))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_queue_size(self) -> int:
        """Get current event queue size."""
        return len(self._queue)

    def get_dead_letter_count(self) -> int:
        """Get dead letter queue size."""
        return len(self._dead_letter)

    def get_dead_letters(self, limit: int = 50) -> List[MLOpsEvent]:
        """Get recent dead letter events."""
        return self._dead_letter[-limit:]

    def reset(self) -> None:
        """Reset state (for testing)."""
        self.stop()
        self._queue.clear()
        self._dead_letter.clear()
        self.event_bus.reset()
