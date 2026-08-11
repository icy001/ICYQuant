"""StressMemory — stress test result memory.

Stores historical stress test results for trend analysis
and model validation over time.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.institutional_risk.stress_engine import StressResult


@dataclass
class StressMemoryEntry:
    """A stress test memory entry."""

    timestamp: float
    scenario_name: str
    portfolio_loss: float
    loss_pct: float
    survival_score: float
    passed: bool
    capital: float
    portfolio_composition_summary: Dict[str, Any] = field(default_factory=dict)


class StressMemory:
    """Stores stress test history for trend analysis.

    Usage::

        memory = StressMemory()
        memory.record(result, capital=100_000_000)
        trend = memory.get_trend("Market Crash -20%")
    """

    def __init__(self, max_entries_per_scenario: int = 200):
        self._entries: Dict[str, List[StressMemoryEntry]] = {}
        self._max_per_scenario = max_entries_per_scenario

    def record(
        self,
        result: StressResult,
        capital: float,
        composition_summary: Optional[Dict[str, Any]] = None,
    ) -> StressMemoryEntry:
        """Record a stress test result."""
        entry = StressMemoryEntry(
            timestamp=time.time(),
            scenario_name=result.scenario_name,
            portfolio_loss=result.portfolio_loss,
            loss_pct=abs(result.portfolio_loss_pct),
            survival_score=result.survival_score_under_stress,
            passed=result.passed,
            capital=capital,
            portfolio_composition_summary=composition_summary or {},
        )

        if result.scenario_name not in self._entries:
            self._entries[result.scenario_name] = []
        self._entries[result.scenario_name].append(entry)

        # trim
        if len(self._entries[result.scenario_name]) > self._max_per_scenario:
            self._entries[result.scenario_name] = (
                self._entries[result.scenario_name][-self._max_per_scenario:]
            )

        return entry

    def get_trend(
        self,
        scenario_name: str,
        last_n: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get trend of stress results for a scenario."""
        entries = self._entries.get(scenario_name, [])[-last_n:]
        return [
            {
                "timestamp": e.timestamp,
                "loss_pct": e.loss_pct,
                "survival": e.survival_score,
                "passed": e.passed,
            }
            for e in entries
        ]

    def compare_recent(
        self,
        scenario_name: str,
        window: int = 10,
    ) -> Dict[str, Any]:
        """Compare recent stress results to historical."""
        entries = self._entries.get(scenario_name, [])
        if len(entries) < window * 2:
            return {"status": "insufficient_data"}

        recent = entries[-window:]
        older = entries[-window * 2:-window]

        recent_avg_loss = sum(e.loss_pct for e in recent) / len(recent)
        older_avg_loss = sum(e.loss_pct for e in older) / len(older)

        recent_avg_survival = sum(e.survival_score for e in recent) / len(recent)
        older_avg_survival = sum(e.survival_score for e in older) / len(older)

        return {
            "recent_avg_loss": recent_avg_loss,
            "older_avg_loss": older_avg_loss,
            "loss_trend": "improving" if recent_avg_loss < older_avg_loss else "deteriorating",
            "recent_avg_survival": recent_avg_survival,
            "older_avg_survival": older_avg_survival,
            "survival_trend": "improving" if recent_avg_survival > older_avg_survival else "deteriorating",
        }

    def clear(self) -> None:
        """Clear all stress memory."""
        self._entries.clear()
