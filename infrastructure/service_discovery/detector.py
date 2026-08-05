"""Phi Accrual failure detector for ICYQuant service discovery.

Provides ``PhiAccrualDetector`` implementing the Phi Accrual failure
detector (Hayashibara et al.) which computes a suspicion level
``phi`` based on the arrival time history of heartbeats. More
stable than fixed-TTL schemes, it adapts to network jitter by
modeling inter-arrival time statistics.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, Optional

logger = logging.getLogger(__name__)


class _DetectorState:
    """Per-instance detector state."""

    __slots__ = (
        "service_name",
        "instance_id",
        "history",
        "last_heartbeat",
        "created_at",
        "state",
    )

    def __init__(self, service_name: str, instance_id: str) -> None:
        self.service_name = service_name
        self.instance_id = instance_id
        self.history: Deque[float] = deque()
        self.last_heartbeat: float = 0.0
        self.created_at: float = time.time()
        self.state: str = "ALIVE"


class PhiAccrualDetector:
    """Phi Accrual failure detector.

    Records heartbeat arrival times per (service, instance) and
    computes a suspicion level ``phi`` based on the distribution of
    inter-arrival intervals. When ``phi`` exceeds the configured
    threshold, the instance is considered suspicious; when it
    exceeds twice the threshold, the instance is considered dead.

    Args:
        threshold: Suspicion threshold (default 8.0).
        min_samples: Minimum samples before phi is computed.
        max_samples: Maximum samples retained per instance.
    """

    STATE_ALIVE = "ALIVE"
    STATE_SUSPICIOUS = "SUSPICIOUS"
    STATE_DEAD = "DEAD"

    def __init__(
        self,
        threshold: float = 8.0,
        min_samples: int = 10,
        max_samples: int = 1000,
    ) -> None:
        self._threshold = float(threshold) if threshold > 0 else 8.0
        self._min_samples = max(int(min_samples), 1)
        self._max_samples = max(int(max_samples), self._min_samples)
        self._lock = threading.RLock()
        self._states: Dict[str, _DetectorState] = {}
        self._record_count = 0
        self._reset_count = 0
        self._dead_count = 0

    # ── Helpers ──

    @staticmethod
    def _make_key(service_name: str, instance_id: str) -> str:
        return f"{service_name}:{instance_id}"

    def _get_or_create(self, key: str, service_name: str, instance_id: str) -> _DetectorState:
        state = self._states.get(key)
        if state is None:
            state = _DetectorState(service_name, instance_id)
            self._states[key] = state
        return state

    # ── Public API ──

    def record_heartbeat(self, service_name: str, instance_id: str) -> None:
        """Record a heartbeat arrival for an instance.

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.
        """
        key = self._make_key(service_name, instance_id)
        now = time.time()
        with self._lock:
            state = self._get_or_create(key, service_name, instance_id)
            if state.last_heartbeat > 0:
                interval = now - state.last_heartbeat
                state.history.append(interval)
                if len(state.history) > self._max_samples:
                    state.history.popleft()
            state.last_heartbeat = now
            state.state = self.STATE_ALIVE
            self._record_count += 1
        logger.debug(
            "Recorded heartbeat for '%s/%s' (samples=%d).",
            service_name,
            instance_id,
            len(state.history),
        )

    def compute_phi(self, service_name: str, instance_id: str) -> float:
        """Compute the current suspicion level (phi).

        Args:
            service_name: The logical service name.
            instance_id: The instance identifier.

        Returns:
            The phi value. Returns 0.0 when insufficient samples or
            no heartbeat has been recorded.
        """
        key = self._make_key(service_name, instance_id)
        now = time.time()
        with self._lock:
            state = self._states.get(key)
            if state is None or state.last_heartbeat <= 0:
                return 0.0
            if len(state.history) < self._min_samples:
                # Not enough samples; use a conservative estimate based
                # on the elapsed time since the last heartbeat.
                elapsed = now - state.last_heartbeat
                return max(elapsed / max(self._threshold, 1.0), 0.0)
            history = list(state.history)
            last_heartbeat = state.last_heartbeat

        mean = sum(history) / len(history)
        if mean <= 0:
            return 0.0
        elapsed = now - last_heartbeat
        if elapsed <= 0:
            return 0.0
        # Phi = -log10(1 - F(elapsed)) where F is the CDF of an
        # exponential distribution with rate 1/mean.
        exponent = -elapsed / mean
        try:
            cdf = 1.0 - math.exp(exponent)
        except OverflowError:
            cdf = 1.0
        if cdf >= 1.0:
            return float("inf")
        if cdf <= 0.0:
            return 0.0
        return -math.log10(1.0 - cdf)

    def is_suspicious(self, service_name: str, instance_id: str) -> bool:
        """Return whether the instance is currently suspicious."""
        phi = self.compute_phi(service_name, instance_id)
        return phi >= self._threshold

    def is_failed(self, service_name: str, instance_id: str) -> bool:
        """Return whether the instance is considered dead.

        An instance is considered dead when ``phi`` exceeds twice the
        configured threshold.
        """
        phi = self.compute_phi(service_name, instance_id)
        return phi >= self._threshold * 2.0

    def get_state(self, service_name: str, instance_id: str) -> str:
        """Return the current state of an instance.

        Returns one of ``ALIVE``, ``SUSPICIOUS``, or ``DEAD``.
        """
        key = self._make_key(service_name, instance_id)
        with self._lock:
            state = self._states.get(key)
            if state is None or state.last_heartbeat <= 0:
                return self.STATE_ALIVE
        phi = self.compute_phi(service_name, instance_id)
        if phi >= self._threshold * 2.0:
            new_state = self.STATE_DEAD
        elif phi >= self._threshold:
            new_state = self.STATE_SUSPICIOUS
        else:
            new_state = self.STATE_ALIVE
        with self._lock:
            state = self._states.get(key)
            if state is not None:
                if state.state != new_state:
                    logger.info(
                        "Detector state for '%s/%s': %s -> %s (phi=%.3f).",
                        service_name,
                        instance_id,
                        state.state,
                        new_state,
                        phi,
                    )
                    state.state = new_state
                    if new_state == self.STATE_DEAD:
                        self._dead_count += 1
        return new_state

    def reset(self, service_name: str, instance_id: str) -> None:
        """Reset the detector state for an instance."""
        key = self._make_key(service_name, instance_id)
        with self._lock:
            state = self._states.pop(key, None)
            self._reset_count += 1
        if state is not None:
            logger.info(
                "Reset detector state for '%s/%s' (samples=%d).",
                service_name,
                instance_id,
                len(state.history),
            )

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the detector."""
        with self._lock:
            states_breakdown: Dict[str, int] = {
                self.STATE_ALIVE: 0,
                self.STATE_SUSPICIOUS: 0,
                self.STATE_DEAD: 0,
            }
            total_samples = 0
            for state in self._states.values():
                states_breakdown[state.state] = (
                    states_breakdown.get(state.state, 0) + 1
                )
                total_samples += len(state.history)
            tracked = len(self._states)
            return {
                "threshold": self._threshold,
                "min_samples": self._min_samples,
                "max_samples": self._max_samples,
                "tracked_instances": tracked,
                "total_samples": total_samples,
                "record_count": self._record_count,
                "reset_count": self._reset_count,
                "dead_count": self._dead_count,
                "by_state": states_breakdown,
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"PhiAccrualDetector(threshold={self._threshold}, "
                f"tracked={len(self._states)})"
            )
