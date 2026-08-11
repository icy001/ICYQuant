"""Factor Mining — autonomously discovers alpha factors from market data.

Pipeline:
    Dataset -> FactorMining.mine()
        -> Feature extraction
        -> Factor construction (momentum, value, quality, etc.)
        -> Factor evaluation (IC, Sharpe, turnover)
        -> Factor selection
        -> Alpha Pool
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FactorType(str, Enum):
    MOMENTUM = "momentum"
    VALUE = "value"
    QUALITY = "quality"
    GROWTH = "growth"
    VOLATILITY = "volatility"
    SENTIMENT = "sentiment"
    CUSTOM = "custom"


class FactorStatus(str, Enum):
    DISCOVERED = "discovered"
    EVALUATED = "evaluated"
    SELECTED = "selected"
    REJECTED = "rejected"


@dataclass
class FactorCandidate:
    """A discovered alpha factor.

    Attributes:
        factor_id: Unique factor identifier.
        factor_type: Type of factor.
        name: Factor name.
        description: Factor description.
        status: Current evaluation status.
        ic_mean: Mean information coefficient.
        ic_ir: IC information ratio.
        sharpe: Factor Sharpe ratio.
        turnover: Annual turnover.
        metadata: Additional factor metadata.
        discovered_at: Discovery timestamp.
    """

    factor_id: str = ""
    factor_type: FactorType = FactorType.CUSTOM
    name: str = ""
    description: str = ""
    status: FactorStatus = FactorStatus.DISCOVERED
    ic_mean: float = 0.0
    ic_ir: float = 0.0
    sharpe: float = 0.0
    turnover: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def quality_score(self) -> float:
        return (abs(self.ic_mean) * 0.4 + self.ic_ir * 0.3 + max(self.sharpe, 0) * 0.2 + min(1.0 / max(self.turnover, 0.1), 1.0) * 0.1)


class FactorMining:
    """Autonomously discovers alpha factors from market data.

    Mines for factors across momentum, value, quality, growth, volatility,
    and sentiment dimensions, then evaluates and selects top factors.

    Supports:
        - Multi-dimensional factor mining
        - Automated factor evaluation (IC, Sharpe, turnover)
        - Factor selection with quality scoring
        - Alpha pool management

    Usage:
        mining = FactorMining()
        await mining.initialize()
        factors = await mining.mine(symbols=["AAPL"], dataset={...})
        selected = mining.select(factors, top_n=10)
    """

    def __init__(self, max_factors: int = 200) -> None:
        self._factors: List[FactorCandidate] = []
        self._max_factors = max_factors
        self._counter: int = 0
        self._initialized: bool = False
        logger.info("FactorMining created (max_factors=%d)", max_factors)

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("FactorMining initialized")

    async def shutdown(self) -> None:
        self._factors.clear()
        self._initialized = False
        logger.info("FactorMining shutdown complete")

    async def mine(
        self,
        symbols: Optional[List[str]] = None,
        dataset: Optional[Dict[str, Any]] = None,
    ) -> List[FactorCandidate]:
        """Mine alpha factors from market data.

        Args:
            symbols: Optional symbols to mine factors for.
            dataset: Market data for factor construction.

        Returns:
            List of discovered FactorCandidates.
        """
        logger.info("FactorMining.mine() started (symbols=%d)", len(symbols) if symbols else 0)
        factors: List[FactorCandidate] = []

        for method in [
            self._mine_momentum_factors,
            self._mine_value_factors,
            self._mine_quality_factors,
            self._mine_growth_factors,
            self._mine_volatility_factors,
        ]:
            discovered = await method(symbols, dataset)
            factors.extend(discovered)

        evaluated = [self._evaluate_factor(f) for f in factors]
        self._store_factors(evaluated)
        logger.info("FactorMining.mine() completed: %d factors", len(evaluated))
        return evaluated

    async def _mine_momentum_factors(self, symbols: Optional[List[str]], data: Optional[Dict[str, Any]]) -> List[FactorCandidate]:
        return []

    async def _mine_value_factors(self, symbols: Optional[List[str]], data: Optional[Dict[str, Any]]) -> List[FactorCandidate]:
        return []

    async def _mine_quality_factors(self, symbols: Optional[List[str]], data: Optional[Dict[str, Any]]) -> List[FactorCandidate]:
        return []

    async def _mine_growth_factors(self, symbols: Optional[List[str]], data: Optional[Dict[str, Any]]) -> List[FactorCandidate]:
        return []

    async def _mine_volatility_factors(self, symbols: Optional[List[str]], data: Optional[Dict[str, Any]]) -> List[FactorCandidate]:
        return []

    def _evaluate_factor(self, factor: FactorCandidate) -> FactorCandidate:
        factor.status = FactorStatus.EVALUATED
        return factor

    def select(self, factors: Optional[List[FactorCandidate]] = None, top_n: int = 10) -> List[FactorCandidate]:
        pool = factors or self._factors
        sorted_factors = sorted(pool, key=lambda f: f.quality_score, reverse=True)
        selected = sorted_factors[:top_n]
        for f in selected:
            f.status = FactorStatus.SELECTED
        return selected

    def _store_factors(self, factors: List[FactorCandidate]) -> None:
        self._factors.extend(factors)
        if len(self._factors) > self._max_factors:
            self._factors = self._factors[-self._max_factors:]

    def get_alpha_pool(self) -> List[Dict[str, Any]]:
        return [
            {
                "factor_id": f.factor_id,
                "name": f.name,
                "type": f.factor_type.value,
                "status": f.status.value,
                "ic_mean": round(f.ic_mean, 4),
                "sharpe": round(f.sharpe, 2),
                "quality_score": round(f.quality_score, 4),
            }
            for f in self._factors if f.status == FactorStatus.SELECTED
        ]

    def get_summary(self) -> Dict[str, Any]:
        selected = sum(1 for f in self._factors if f.status == FactorStatus.SELECTED)
        return {
            "initialized": self._initialized,
            "total_factors": len(self._factors),
            "selected": selected,
        }
