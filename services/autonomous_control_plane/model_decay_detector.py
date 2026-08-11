"""
Model Decay Detector — Detects alpha/strategy performance decay.

Monitors expected vs actual performance to identify models whose
predictive power is deteriorating over time.
"""

from __future__ import annotations

import time
import logging
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class ModelDecayDetector:
    """
    Detects model performance decay over time.

    Compares expected performance (e.g., Sharpe from backtest) with
    realized performance to identify alpha decay.
    """

    def __init__(self, window_size: int = 100, decay_threshold: float = 0.3):
        self._window_size = window_size
        self._decay_threshold = decay_threshold
        self._observations: dict[str, deque[float]] = {}
        self._expected: dict[str, float] = {}

    def set_expected(self, model_id: str, expected_sharpe: float):
        """Set the expected performance (e.g., from backtest)."""
        self._expected[model_id] = expected_sharpe

    def observe(self, model_id: str, realized_sharpe: float):
        """Record a realized performance observation."""
        obs = self._observations.setdefault(model_id, deque(maxlen=self._window_size))
        obs.append(realized_sharpe)

    def compute_decay(self, model_id: str) -> float:
        """
        Compute the decay rate for a model.

        Returns decay as a fraction: 0.0 = no decay, 1.0 = complete decay.
        """
        expected = self._expected.get(model_id, 0.0)
        obs = self._observations.get(model_id, deque())
        if not obs or expected <= 0:
            return 0.0

        recent_avg = sum(list(obs)[-20:]) / min(20, len(obs))  # Last 20 obs
        decay = 1.0 - min(1.0, recent_avg / max(expected, 0.01))
        return max(0.0, decay)

    def is_decaying(self, model_id: str) -> tuple[bool, float, str]:
        """
        Check if a model is experiencing decay.

        Returns (is_decaying, decay_rate, status).
        """
        decay = self.compute_decay(model_id)

        if decay > 0.5:
            return True, decay, "severe_decay"
        elif decay > self._decay_threshold:
            return True, decay, "decaying"
        elif decay > 0.1:
            return False, decay, "early_warning"
        return False, decay, "healthy"

    def stats(self) -> dict:
        decaying = []
        for mid in self._expected:
            is_decaying, rate, status = self.is_decaying(mid)
            if is_decaying:
                decaying.append({"model_id": mid, "decay_rate": rate, "status": status})
        return {
            "models_tracked": len(self._expected),
            "decaying_models": len(decaying),
            "details": decaying,
        }
