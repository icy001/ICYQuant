"""Discovery Memory — Long-term memory for research discoveries.

Remembers successful and failed research to prevent repeating
historically rejected hypotheses and to bias toward known patterns.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DiscoveryMemory:
    """Stores research history for similarity-aware discovery.

    Prevents the autonomous system from endlessly retesting
    previously rejected hypotheses by maintaining a memory of:
        - Successful research patterns
        - Failed hypotheses and why
        - Rejected factors
        - Successful factor constructions
        - Failed strategy approaches
    """

    def __init__(self) -> None:
        self._successes: List[Dict[str, Any]] = []
        self._failures: List[Dict[str, Any]] = []
        self._rejected_hypotheses: List[Dict[str, Any]] = []
        self._successful_factors: List[Dict[str, Any]] = []
        self._failed_factors: List[Dict[str, Any]] = []

    async def start(self) -> None:
        logger.info("Discovery Memory started")

    async def stop(self) -> None:
        logger.info("Discovery Memory stopped")

    async def record_cycle(
        self,
        cycle_id: str,
        results: Dict[str, Any],
    ) -> None:
        if results.get("success"):
            self._successes.append({
                "cycle_id": cycle_id,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "results": results,
            })

    async def record_failure(
        self,
        hypothesis: Dict[str, Any],
        reason: str,
    ) -> None:
        self._failures.append({
            "hypothesis_id": hypothesis.get("hypothesis_id", ""),
            "statement": hypothesis.get("statement", ""),
            "reason": reason,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        })

    async def find_similar(
        self,
        hypothesis: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        statement = hypothesis.get("statement", "")
        for failure in self._failures:
            if failure.get("statement") == statement:
                return failure
        return None

    async def is_novel(self, hypothesis: Dict[str, Any]) -> bool:
        return await self.find_similar(hypothesis) is None

    async def health(self) -> Dict[str, Any]:
        return {
            "successes": len(self._successes),
            "failures": len(self._failures),
            "rejected_hypotheses": len(self._rejected_hypotheses),
        }
