"""Health policies for ICYQuant service discovery.

Provides ``HealthPolicy`` and concrete implementations for deciding
whether a service instance is healthy based on a sequence of check
results. Includes ``AlwaysHealthyPolicy``, ``ThresholdPolicy``,
``ConsecutiveFailurePolicy``, ``AdaptivePolicy``, and a
``PolicyFactory`` for constructing policies by name.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from typing import Any, Deque, Dict, List, Optional
from collections import deque

logger = logging.getLogger(__name__)


class HealthPolicy(ABC):
    """Abstract base class for health policies."""

    @abstractmethod
    def is_healthy(self, checks: List[Dict[str, Any]]) -> bool:
        """Evaluate whether the instance is healthy.

        Args:
            checks: A list of recent check result dictionaries, each
                expected to contain a ``success`` boolean.

        Returns:
            True if the instance is considered healthy.
        """

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the policy."""
        return {"policy_type": type(self).__name__}


class AlwaysHealthyPolicy(HealthPolicy):
    """Policy that always reports healthy."""

    def is_healthy(self, checks: List[Dict[str, Any]]) -> bool:
        """Always return True."""
        return True

    def get_stats(self) -> Dict[str, Any]:
        return {"policy_type": "always_healthy"}


class ThresholdPolicy(HealthPolicy):
    """Policy based on a success-ratio threshold.

    Healthy when the ratio of successful checks to total checks is
    greater than or equal to ``threshold``.

    Args:
        threshold: Minimum success ratio in [0.0, 1.0].
    """

    def __init__(self, threshold: float = 0.5) -> None:
        self._threshold = max(0.0, min(float(threshold), 1.0))
        self._lock = threading.RLock()
        self._eval_count = 0

    def is_healthy(self, checks: List[Dict[str, Any]]) -> bool:
        """Return True if the success ratio meets the threshold."""
        with self._lock:
            self._eval_count += 1
        if not checks:
            return True
        successes = sum(
            1 for c in checks if c.get("success", False)
        )
        ratio = successes / len(checks)
        return ratio >= self._threshold

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "policy_type": "threshold",
                "threshold": self._threshold,
                "eval_count": self._eval_count,
            }


class ConsecutiveFailurePolicy(HealthPolicy):
    """Policy based on consecutive failures.

    Unhealthy when the number of consecutive trailing failures
    exceeds ``max_failures``.

    Args:
        max_failures: Maximum allowed consecutive failures.
    """

    def __init__(self, max_failures: int = 3) -> None:
        self._max_failures = max(int(max_failures), 1)
        self._lock = threading.RLock()
        self._eval_count = 0
        self._current_streak = 0

    def is_healthy(self, checks: List[Dict[str, Any]]) -> bool:
        """Return True if consecutive failures are within tolerance."""
        with self._lock:
            self._eval_count += 1
            streak = 0
            for check in reversed(checks):
                if not check.get("success", False):
                    streak += 1
                else:
                    break
            self._current_streak = streak
            return streak < self._max_failures

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "policy_type": "consecutive_failure",
                "max_failures": self._max_failures,
                "eval_count": self._eval_count,
                "current_streak": self._current_streak,
            }


class AdaptivePolicy(HealthPolicy):
    """Adaptive policy that adjusts based on recent history.

    Maintains a sliding window of recent check outcomes and
    considers the instance unhealthy when the failure ratio within
    the window exceeds ``failure_ratio``.

    Args:
        window_size: Number of recent checks to consider.
        failure_ratio: Maximum tolerated failure ratio in [0.0, 1.0].
    """

    def __init__(
        self,
        window_size: int = 10,
        failure_ratio: float = 0.3,
    ) -> None:
        self._window_size = max(int(window_size), 1)
        self._failure_ratio = max(0.0, min(float(failure_ratio), 1.0))
        self._lock = threading.RLock()
        self._window: Deque[bool] = deque(maxlen=self._window_size)
        self._eval_count = 0

    def is_healthy(self, checks: List[Dict[str, Any]]) -> bool:
        """Return True if the failure ratio is within tolerance."""
        with self._lock:
            self._eval_count += 1
            for check in checks:
                self._window.append(bool(check.get("success", False)))
            if not self._window:
                return True
            failures = sum(1 for ok in self._window if not ok)
            ratio = failures / len(self._window)
            return ratio <= self._failure_ratio

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            failures = sum(1 for ok in self._window if not ok)
            return {
                "policy_type": "adaptive",
                "window_size": self._window_size,
                "failure_ratio": self._failure_ratio,
                "current_window_size": len(self._window),
                "current_failures": failures,
                "eval_count": self._eval_count,
            }


class PolicyFactory:
    """Factory for creating health policies by name."""

    @staticmethod
    def create(policy_type: str = "consecutive", **kwargs: Any) -> HealthPolicy:
        """Create a health policy of the given type.

        Args:
            policy_type: One of ``always``, ``threshold``,
                ``consecutive``, ``adaptive``.
            **kwargs: Keyword arguments forwarded to the policy.

        Returns:
            A ``HealthPolicy`` instance.

        Raises:
            ValueError: If the policy type is unknown.
        """
        policy_type = (policy_type or "consecutive").lower().strip()
        if policy_type in ("always", "always_healthy", "alwayshealthy"):
            return AlwaysHealthyPolicy()
        if policy_type in ("threshold", "threshold_policy"):
            return ThresholdPolicy(threshold=kwargs.get("threshold", 0.5))
        if policy_type in ("consecutive", "consecutive_failure", "consecutivefailure"):
            return ConsecutiveFailurePolicy(
                max_failures=kwargs.get("max_failures", 3)
            )
        if policy_type in ("adaptive", "adaptive_policy"):
            return AdaptivePolicy(
                window_size=kwargs.get("window_size", 10),
                failure_ratio=kwargs.get("failure_ratio", 0.3),
            )
        raise ValueError(f"Unknown policy type: {policy_type!r}")
