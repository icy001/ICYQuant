"""Candidate Registry — Unified registry for all research candidates.

Tracks: Opportunity → Hypothesis → Factor → Alpha → Strategy → Experiment
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class CandidateRegistry:
    """Unified registry for all research candidates across the pipeline."""

    def __init__(self) -> None:
        self._opportunities: List[Dict[str, Any]] = []
        self._hypotheses: List[Dict[str, Any]] = []
        self._factors: List[Dict[str, Any]] = []
        self._alphas: List[Dict[str, Any]] = []
        self._strategies: List[Dict[str, Any]] = []
        self._experiments: List[Dict[str, Any]] = []

    async def register(self, candidate: Dict[str, Any]) -> str:
        candidate["registered_at"] = datetime.now(timezone.utc).isoformat()
        ctype = candidate.get("type", "unknown")

        if ctype == "opportunity" or "opportunity_id" in candidate:
            self._opportunities.append(candidate)
        elif ctype == "hypothesis" or "hypothesis_id" in candidate:
            self._hypotheses.append(candidate)
        elif ctype == "factor" or "factor_id" in candidate:
            self._factors.append(candidate)
        elif ctype == "alpha" or "alpha_id" in candidate:
            self._alphas.append(candidate)
        elif ctype == "strategy" or "strategy_id" in candidate:
            self._strategies.append(candidate)
        else:
            self._experiments.append(candidate)

        return candidate.get("candidate_id", "")

    def query(self, ctype: str) -> List[Dict[str, Any]]:
        maps = {
            "opportunity": self._opportunities,
            "hypothesis": self._hypotheses,
            "factor": self._factors,
            "alpha": self._alphas,
            "strategy": self._strategies,
            "experiment": self._experiments,
        }
        return maps.get(ctype, [])

    async def health(self) -> Dict[str, Any]:
        return {
            "opportunities": len(self._opportunities),
            "hypotheses": len(self._hypotheses),
            "factors": len(self._factors),
            "alphas": len(self._alphas),
            "strategies": len(self._strategies),
            "experiments": len(self._experiments),
        }
