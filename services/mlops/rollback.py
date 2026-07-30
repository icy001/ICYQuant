"""
Automatic Rollback Manager.

Monitors deployed models for anomalies and automatically rolls back
to a previous stable version when safety thresholds are breached.

Triggers include:
- Error rate spikes
- Latency degradation
- Prediction drift (PSI > threshold)
- Sharpe collapse
- Manual rollback requests
"""

import enum
import time
import uuid
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RollbackStatus(str, enum.Enum):
    """Status of a rollback event."""
    TRIGGERED = "triggered"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERTED = "reverted"  # rollback was rolled back


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RollbackConfig:
    """Configuration for automatic rollback."""

    # Error thresholds
    max_error_rate: float = 0.05
    error_rate_window_minutes: float = 5.0
    error_spike_factor: float = 3.0  # 3x baseline error rate

    # Latency thresholds
    max_latency_p99_ms: float = 500.0
    latency_increase_factor: float = 2.0

    # Prediction drift
    max_prediction_psi: float = 0.3

    # Performance degradation
    sharpe_min_threshold: float = 0.3
    sharpe_collapse_pct: float = 0.5  # 50% drop = rollback

    # Safety
    require_confirmation: bool = False
    confirmation_timeout_seconds: float = 300.0
    cool_down_seconds: float = 3600.0  # 1 hour between rollbacks

    # Rollback behavior
    revert_to_previous: bool = True
    notify_on_rollback: bool = True
    create_incident: bool = True


@dataclass
class RollbackRule:
    """A single rollback trigger rule."""

    rule_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    metric: str = ""  # error_rate, latency_p99, prediction_psi, sharpe
    operator: str = ">"  # >, <, >=, <=
    threshold: float = 0.0
    enabled: bool = True
    severity: str = "high"  # low, medium, high, critical
    cooldown_seconds: float = 3600.0

    def evaluate(self, current_value: float, baseline_value: float = 0) -> bool:
        """Check if the rule is triggered."""
        if not self.enabled:
            return False

        if self.metric in ("error_rate", "prediction_psi", "latency_p99"):
            # Use factor-based comparison
            if baseline_value > 0:
                factor = current_value / baseline_value
                if self.operator == ">":
                    return factor > self.threshold
                elif self.operator == ">=":
                    return factor >= self.threshold
        else:
            # Direct threshold comparison
            if self.operator == ">":
                return current_value > self.threshold
            elif self.operator == ">=":
                return current_value >= self.threshold
            elif self.operator == "<":
                return current_value < self.threshold
            elif self.operator == "<=":
                return current_value <= self.threshold

        return False


@dataclass
class RollbackEvent:
    """A single rollback event."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    model_name: str = ""
    from_version: str = ""
    to_version: str = ""

    # Trigger
    triggered_rule: Optional[str] = None
    trigger_reason: str = ""
    trigger_value: float = 0.0
    trigger_threshold: float = 0.0

    # Status
    status: RollbackStatus = RollbackStatus.TRIGGERED

    # Timing
    triggered_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    # Confirmation
    confirmed: bool = False
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[float] = None

    # Result
    success: bool = False
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "model_name": self.model_name,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "triggered_rule": self.triggered_rule,
            "trigger_reason": self.trigger_reason,
            "status": self.status.value,
            "triggered_at": self.triggered_at,
            "confirmed": self.confirmed,
            "success": self.success,
        }


# ---------------------------------------------------------------------------
# Rollback Manager
# ---------------------------------------------------------------------------

class RollbackManager:
    """Manages automatic and manual model rollbacks.

    Monitors model health metrics and triggers rollback when
    safety thresholds are breached. Maintains a version history
    to enable reversion to any previous stable version.

    Usage::

        rm = RollbackManager(config, model_registry)
        rm.register_model("Alpha_v38", "1.0.0")
        rm.record_metric("Alpha_v38", "error_rate", 0.15)
        # If 0.15 > threshold, rollback triggers
    """

    def __init__(
        self,
        config: RollbackConfig,
        model_registry: Any = None,
        deployment_manager: Any = None,
    ):
        self.config = config
        self.model_registry = model_registry
        self.deployment_manager = deployment_manager

        # Per-model state
        self._versions: Dict[str, List[str]] = {}  # model → version history
        self._current_version: Dict[str, str] = {}  # model → current version
        self._baseline_metrics: Dict[str, Dict[str, float]] = {}
        self._rules: Dict[str, RollbackRule] = {}
        self._events: List[RollbackEvent] = []
        self._last_rollback_time: Dict[str, float] = {}

        self._on_rollback_callbacks: List[Callable] = []

        # Default rules
        self._init_default_rules()

    def _init_default_rules(self) -> None:
        """Initialize default rollback rules."""
        defaults = [
            RollbackRule(
                name="error_rate_spike",
                description="Error rate exceeds 3x baseline",
                metric="error_rate",
                operator=">",
                threshold=self.config.error_spike_factor,
                severity="high",
            ),
            RollbackRule(
                name="prediction_drift",
                description="Prediction PSI exceeds threshold",
                metric="prediction_psi",
                operator=">",
                threshold=self.config.max_prediction_psi,
                severity="high",
            ),
            RollbackRule(
                name="latency_degradation",
                description="P99 latency exceeds 2x baseline",
                metric="latency_p99",
                operator=">",
                threshold=self.config.latency_increase_factor,
                severity="medium",
            ),
            RollbackRule(
                name="sharpe_collapse",
                description="Sharpe ratio drops below critical threshold",
                metric="sharpe",
                operator="<",
                threshold=self.config.sharpe_min_threshold,
                severity="critical",
            ),
        ]
        for rule in defaults:
            self._rules[rule.name] = rule

    # ------------------------------------------------------------------
    # Model Registration
    # ------------------------------------------------------------------

    def register_model(
        self,
        model_name: str,
        version: str,
        baseline_metrics: Optional[Dict[str, float]] = None,
    ) -> None:
        """Register a model for rollback monitoring.

        Args:
            model_name: Model identifier.
            version: Current deployed version.
            baseline_metrics: Baseline metrics (from training/evaluation).
        """
        if model_name not in self._versions:
            self._versions[model_name] = []
        if version not in self._versions[model_name]:
            self._versions[model_name].append(version)

        self._current_version[model_name] = version

        if baseline_metrics:
            self._baseline_metrics[model_name] = baseline_metrics

        logger.info(f"Model registered for rollback: {model_name} v{version}")

    def add_version(self, model_name: str, version: str) -> None:
        """Add a version to the history for a model."""
        if model_name not in self._versions:
            self._versions[model_name] = []
        if version not in self._versions[model_name]:
            self._versions[model_name].append(version)

    # ------------------------------------------------------------------
    # Metric Recording & Monitoring
    # ------------------------------------------------------------------

    def record_metric(
        self, model_name: str, metric_name: str, value: float
    ) -> Optional[RollbackEvent]:
        """Record a metric and check against rollback rules.

        Args:
            model_name: Model identifier.
            metric_name: Metric name (error_rate, latency_p99, etc.).
            value: Current metric value.

        Returns:
            RollbackEvent if a rollback was triggered, None otherwise.
        """
        if model_name not in self._current_version:
            return None

        # Check cooldown
        last_time = self._last_rollback_time.get(model_name, 0)
        if time.time() - last_time < self.config.cool_down_seconds:
            return None

        baseline = self._baseline_metrics.get(model_name, {}).get(metric_name, 0)

        # Check all applicable rules
        for rule in self._rules.values():
            if rule.metric != metric_name:
                continue
            if not rule.evaluate(value, baseline):
                continue

            # Rule triggered!
            return self._trigger_rollback(
                model_name=model_name,
                from_version=self._current_version[model_name],
                to_version=self._get_previous_version(model_name),
                rule_name=rule.name,
                reason=f"{rule.description}: {metric_name}={value:.4f} "
                       f"(threshold={rule.threshold}, baseline={baseline:.4f})",
                trigger_value=value,
                trigger_threshold=rule.threshold,
            )

        return None

    def check_all_metrics(
        self, model_name: str, metrics: Dict[str, float]
    ) -> List[RollbackEvent]:
        """Check multiple metrics at once.

        Returns:
            List of triggered RollbackEvents.
        """
        events = []
        for metric_name, value in metrics.items():
            event = self.record_metric(model_name, metric_name, value)
            if event:
                events.append(event)
        return events

    # ------------------------------------------------------------------
    # Rollback Execution
    # ------------------------------------------------------------------

    def rollback(
        self,
        model_name: str,
        to_version: Optional[str] = None,
        reason: str = "Manual rollback",
    ) -> Optional[RollbackEvent]:
        """Manually trigger a rollback.

        Args:
            model_name: Model to rollback.
            to_version: Target version (defaults to previous).
            reason: Human-readable reason.

        Returns:
            RollbackEvent if successful.
        """
        current = self._current_version.get(model_name)
        if not current:
            logger.error(f"Model {model_name} not registered")
            return None

        target = to_version or self._get_previous_version(model_name)
        if not target:
            logger.error(f"No previous version available for {model_name}")
            return None

        if target == current:
            logger.warning(f"Target version {target} is same as current")
            return None

        return self._trigger_rollback(
            model_name=model_name,
            from_version=current,
            to_version=target,
            rule_name="manual",
            reason=reason,
            trigger_value=0.0,
            trigger_threshold=0.0,
        )

    def _trigger_rollback(
        self,
        model_name: str,
        from_version: str,
        to_version: str,
        rule_name: str,
        reason: str,
        trigger_value: float,
        trigger_threshold: float,
    ) -> RollbackEvent:
        """Execute a rollback."""
        event = RollbackEvent(
            model_name=model_name,
            from_version=from_version,
            to_version=to_version,
            triggered_rule=rule_name,
            trigger_reason=reason,
            trigger_value=trigger_value,
            trigger_threshold=trigger_threshold,
            status=RollbackStatus.TRIGGERED,
        )

        logger.warning(
            f"ROLLBACK TRIGGERED: {model_name} v{from_version} → v{to_version}. "
            f"Rule: {rule_name}, Reason: {reason}"
        )

        # Always record the event
        self._events.append(event)

        # Check if confirmation required
        if self.config.require_confirmation:
            logger.info(f"Rollback {event.event_id} awaiting confirmation")
            return event

        # Auto-confirm
        event.confirmed = True
        return self._execute_rollback(event)

    def confirm_rollback(self, event_id: str, confirmed_by: str = "system") -> bool:
        """Confirm a pending rollback."""
        for event in self._events:
            if event.event_id == event_id and not event.confirmed:
                event.confirmed = True
                event.confirmed_by = confirmed_by
                event.confirmed_at = time.time()
                return self._execute_rollback(event)
        return False

    def _execute_rollback(self, event: RollbackEvent) -> RollbackEvent:
        """Execute the actual rollback."""
        event.status = RollbackStatus.IN_PROGRESS

        try:
            # Execute via model registry
            if self.model_registry:
                self.model_registry.demote(
                    event.model_name, event.from_version, "archived"
                )
                self.model_registry.promote(
                    event.model_name, event.to_version, "production"
                )

            # Update current version tracking
            self._current_version[event.model_name] = event.to_version
            self._last_rollback_time[event.model_name] = time.time()

            event.status = RollbackStatus.COMPLETED
            event.success = True
            event.completed_at = time.time()

            logger.info(
                f"Rollback {event.event_id} completed: "
                f"{event.model_name} v{event.to_version} is now production"
            )

            self._notify_rollback(event)

        except Exception as e:
            event.status = RollbackStatus.FAILED
            event.success = False
            event.error_message = str(e)
            logger.error(f"Rollback {event.event_id} failed: {e}")

        return event

    # ------------------------------------------------------------------
    # Rules Management
    # ------------------------------------------------------------------

    def add_rule(self, rule: RollbackRule) -> None:
        """Add a custom rollback rule."""
        self._rules[rule.name] = rule

    def remove_rule(self, rule_name: str) -> bool:
        """Remove a rollback rule."""
        if rule_name in self._rules:
            del self._rules[rule_name]
            return True
        return False

    def get_rules(self) -> List[RollbackRule]:
        """Get all configured rollback rules."""
        return list(self._rules.values())

    def enable_rule(self, rule_name: str, enabled: bool = True) -> bool:
        """Enable or disable a rollback rule."""
        if rule_name in self._rules:
            self._rules[rule_name].enabled = enabled
            return True
        return False

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_events(
        self,
        model_name: Optional[str] = None,
        status: Optional[RollbackStatus] = None,
        limit: int = 50,
    ) -> List[RollbackEvent]:
        """Get rollback events with filters."""
        events = self._events
        if model_name:
            events = [e for e in events if e.model_name == model_name]
        if status:
            events = [e for e in events if e.status == status]
        return sorted(events, key=lambda e: e.triggered_at, reverse=True)[:limit]

    def get_current_version(self, model_name: str) -> Optional[str]:
        """Get the current deployed version of a model."""
        return self._current_version.get(model_name)

    def get_version_history(self, model_name: str) -> List[str]:
        """Get the version history for a model."""
        return list(self._versions.get(model_name, []))

    def is_in_cooldown(self, model_name: str) -> bool:
        """Check if a model is in rollback cooldown."""
        last_time = self._last_rollback_time.get(model_name, 0)
        return (time.time() - last_time) < self.config.cool_down_seconds

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_rollback(self, callback: Callable) -> None:
        """Register a callback for rollback events."""
        self._on_rollback_callbacks.append(callback)

    def _notify_rollback(self, event: RollbackEvent) -> None:
        for cb in self._on_rollback_callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"Rollback callback error: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_previous_version(self, model_name: str) -> Optional[str]:
        """Get the version before the current one."""
        versions = self._versions.get(model_name, [])
        current = self._current_version.get(model_name)
        if not current or len(versions) < 2:
            return None

        # Find current index and return previous
        try:
            idx = versions.index(current)
            if idx > 0:
                return versions[idx - 1]
        except ValueError:
            pass

        # Fallback: return the version before last
        return versions[-2] if len(versions) >= 2 else None

    def reset(self) -> None:
        """Reset state (for testing)."""
        self._versions.clear()
        self._current_version.clear()
        self._baseline_metrics.clear()
        self._events.clear()
        self._last_rollback_time.clear()
        self._init_default_rules()
