"""Experiment Planner — Plans experiments to test hypotheses.

Converts research plans into executable experiment configurations
with defined parameters, metrics, and success criteria.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ExperimentPlanner:

    def __init__(self) -> None:
        self._plans: List[Dict[str, Any]] = []

    async def plan(
        self,
        research_plan: Dict[str, Any],
        hypothesis: Dict[str, Any],
    ) -> Dict[str, Any]:
        exp_id = f"exp_plan_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        plan = {
            "experiment_plan_id": exp_id,
            "hypothesis_id": hypothesis.get("hypothesis_id", ""),
            "research_plan_id": research_plan.get("plan_id", ""),
            "experiments": research_plan.get("experiments", []),
            "backtest_config": research_plan.get("backtest_config", {}),
            "validation_rules": research_plan.get("validation_rules", {}),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "planned",
        }
        self._plans.append(plan)
        logger.info("Experiment plan created: %s", exp_id)
        return plan
