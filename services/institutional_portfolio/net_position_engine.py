"""
Net Position Engine — Final Portfolio-Level Position Computation

Combines position netting, aggregation, conflict resolution, and
target computation into a single pipeline producing final net positions.

Pipeline:
    Strategy Positions → Net → Aggregate → Resolve → Target → Net Positions
"""

import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class NetPositionEngine:
    """
    Unified engine that produces final portfolio net positions.

    Orchestrates the full position pipeline:
    1. Collect strategy positions
    2. Net across strategies
    3. Aggregate exposure metrics
    4. Resolve conflicts
    5. Compute target positions
    """

    def __init__(
        self,
        engine_id: Optional[str] = None,
        netting_engine=None,
        aggregator=None,
        conflict_resolver=None,
        target_engine=None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.engine_id = engine_id or f"npe-{uuid.uuid4().hex[:12]}"
        self._netting = netting_engine
        self._aggregator = aggregator
        self._conflict_resolver = conflict_resolver
        self._target_engine = target_engine
        self.config = config or {}

    def compute(
        self,
        strategy_positions: Dict[str, Dict[str, float]],
        priorities: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Run full position pipeline and return final net positions."""
        result = {}

        # Step 1: Set & net
        if self._netting:
            for sid, pos in strategy_positions.items():
                self._netting.set_strategy_positions(sid, pos)
            netted = self._netting.net()
            result["netted"] = {a: p.net_position for a, p in netted.items()}

        # Step 2: Aggregate
        if self._aggregator:
            aggregated = self._aggregator.aggregate(strategy_positions)
            result["gross_exposure"] = self._aggregator.get_gross()
            result["net_exposure"] = self._aggregator.get_net()
            result["long_exposure"] = self._aggregator.get_long_exposure()
            result["short_exposure"] = self._aggregator.get_short_exposure()

        # Step 3: Compute targets
        if self._target_engine and "netted" in result:
            targets = self._target_engine.compute(result["netted"])
            result["targets"] = {
                a: {"weight": t.target_weight, "change": t.required_change}
                for a, t in targets.items()
            }

        return result
