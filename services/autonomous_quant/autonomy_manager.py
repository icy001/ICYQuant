"""Autonomy Manager — Lifecycle and state management for autonomous subsystems.

Tracks discovery pipeline components, manages subsystem health, and
provides coordination between scanning, hypothesis, research, and
strategy generation stages.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .autonomous_platform import AutonomyConfig

logger = logging.getLogger(__name__)


@dataclass
class PipelineStage:
    """A stage in the autonomous research pipeline."""

    name: str
    status: str = "idle"
    last_run: Optional[datetime] = None
    runs_completed: int = 0
    runs_failed: int = 0
    items_processed: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AutonomyManager:
    """Autonomy Manager — manages the discovery pipeline lifecycle.

    Pipeline stages:
        Scanner → Opportunity → Hypothesis → Research → Factor →
        Alpha → Strategy → Backtest → Validation → Registry

    Tracks each stage's status, throughput, and health.
    """

    def __init__(self, config: "AutonomyConfig") -> None:
        self.config = config
        self._stages: Dict[str, PipelineStage] = {}
        self._started = False
        self._start_time: Optional[datetime] = None

    async def start(self) -> None:
        self._start_time = datetime.now(timezone.utc)
        self._started = True
        self._init_stages()
        logger.info("Autonomy Manager started (%d stages)", len(self._stages))

    async def stop(self) -> None:
        self._started = False
        logger.info("Autonomy Manager stopped")

    def _init_stages(self) -> None:
        """Initialize all pipeline stages."""
        stages = [
            "market_scanner",
            "anomaly_detector",
            "regime_detector",
            "opportunity_detector",
            "hypothesis_generator",
            "hypothesis_validator",
            "research_planner",
            "experiment_planner",
            "factor_miner",
            "factor_validator",
            "alpha_discovery",
            "alpha_validator",
            "strategy_generator",
            "strategy_validator",
            "backtest_orchestrator",
            "candidate_registry",
        ]
        for name in stages:
            self._stages[name] = PipelineStage(name=name, status="idle")

    def record_stage_run(
        self,
        name: str,
        success: bool,
        items: int = 1,
    ) -> None:
        """Record a pipeline stage execution."""
        stage = self._stages.get(name)
        if not stage:
            return
        stage.last_run = datetime.now(timezone.utc)
        stage.runs_completed += 1
        if not success:
            stage.runs_failed += 1
        stage.items_processed += items

    def get_stage(self, name: str) -> Optional[PipelineStage]:
        return self._stages.get(name)

    def get_all_stages(self) -> Dict[str, PipelineStage]:
        return dict(self._stages)

    async def health(self) -> Dict[str, Any]:
        total = len(self._stages)
        healthy = sum(1 for s in self._stages.values() if s.runs_failed == 0)

        return {
            "started": self._started,
            "stages_total": total,
            "stages_healthy": healthy,
            "stages": {
                name: {
                    "status": s.status,
                    "runs": s.runs_completed,
                    "failed": s.runs_failed,
                    "processed": s.items_processed,
                    "last_run": s.last_run.isoformat() if s.last_run else None,
                }
                for name, s in self._stages.items()
            },
        }
