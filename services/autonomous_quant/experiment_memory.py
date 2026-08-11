"""Experiment Memory — Records experiment configurations and results for reproducibility."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class ExperimentMemory:
    """Stores experiment configurations and results for reproducibility."""

    def __init__(self) -> None:
        self._experiments: List[Dict[str, Any]] = []

    async def record(
        self,
        experiment_id: str,
        config: Dict[str, Any],
        result: Dict[str, Any],
    ) -> None:
        self._experiments.append({
            "experiment_id": experiment_id,
            "config": config,
            "result": result,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })

    async def get(self, experiment_id: str) -> Dict[str, Any]:
        for exp in self._experiments:
            if exp["experiment_id"] == experiment_id:
                return exp
        return {}

    async def health(self) -> Dict[str, Any]:
        return {"experiments_stored": len(self._experiments)}
