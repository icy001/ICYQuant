"""
Risk Engine Adapter — Connects Strategy Platform to the Risk Engine.

Provides interface for pre-trade risk checks, position limits,
and risk constraint validation before order intent execution.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RiskCheckType(str, Enum):
    """Types of risk checks."""
    PRE_TRADE = "pre_trade"
    POSITION_LIMIT = "position_limit"
    EXPOSURE = "exposure"
    LEVERAGE = "leverage"
    CONCENTRATION = "concentration"
    VOLATILITY = "volatility"
    LIQUIDITY = "liquidity"
    COMPLIANCE = "compliance"


@dataclass
class RiskCheckRequest:
    """Request for risk validation."""
    request_id: str
    strategy_id: str
    check_types: list[RiskCheckType]
    order_intent: Optional[dict[str, Any]] = None  # OrderIntent serialized
    portfolio_id: Optional[str] = None
    instrument: Optional[str] = None
    quantity: float = 0.0
    price: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RiskCheckResult:
    """Result of a risk validation check."""
    request_id: str
    strategy_id: str
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)  # check_type -> passed
    violations: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    check_latency_ms: float = 0.0
    error: Optional[str] = None


class RiskEngineAdapter:
    """
    Adapter for the Risk Engine.

    Performs pre-trade risk checks, position limit validation,
    and exposure constraint verification before orders reach OMS.

    Usage::

        adapter = RiskEngineAdapter()
        await adapter.initialize()
        result = await adapter.check_risk(RiskCheckRequest(
            request_id="risk_001",
            strategy_id="strat_001",
            check_types=[RiskCheckType.PRE_TRADE, RiskCheckType.POSITION_LIMIT],
            instrument="AAPL",
            quantity=1000,
        ))
    """

    def __init__(self) -> None:
        self._results: dict[str, RiskCheckResult] = {}
        self._counter: int = 0
        self._initialized: bool = False

    async def initialize(self) -> None:
        """Initialize the risk engine adapter."""
        self._initialized = True
        logger.info("RiskEngineAdapter initialized.")

    async def stop(self) -> None:
        """Stop the adapter."""
        self._initialized = False
        logger.info("RiskEngineAdapter stopped.")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def check_risk(self, request: RiskCheckRequest) -> RiskCheckResult:
        """Perform risk validation checks."""
        self._counter += 1
        request_id = request.request_id or f"risk_{self._counter:06d}"

        start = asyncio.get_event_loop().time()

        # Simulate risk checks
        checks: dict[str, bool] = {}
        violations: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        for check_type in request.check_types:
            # All checks pass in simulation
            checks[check_type.value] = True

        all_passed = all(checks.values())

        latency = (asyncio.get_event_loop().time() - start) * 1000

        result = RiskCheckResult(
            request_id=request_id,
            strategy_id=request.strategy_id,
            passed=all_passed,
            checks=checks,
            violations=violations,
            warnings=warnings,
            check_latency_ms=latency,
        )
        self._results[request_id] = result

        logger.debug(f"Risk check: {request.strategy_id} -> {'PASS' if all_passed else 'FAIL'}")
        return result

    async def check_pre_trade(
        self,
        strategy_id: str,
        instrument: str,
        quantity: float,
        price: Optional[float] = None,
    ) -> RiskCheckResult:
        """Convenience method for pre-trade risk check."""
        request = RiskCheckRequest(
            request_id=f"pt_{self._counter + 1:06d}",
            strategy_id=strategy_id,
            check_types=[RiskCheckType.PRE_TRADE, RiskCheckType.POSITION_LIMIT],
            instrument=instrument,
            quantity=quantity,
            price=price,
        )
        return await self.check_risk(request)

    async def get_result(self, request_id: str) -> Optional[RiskCheckResult]:
        """Get a previous risk check result."""
        return self._results.get(request_id)

    async def get_last_result(self, strategy_id: str) -> Optional[RiskCheckResult]:
        """Get the most recent risk check result for a strategy."""
        results = [r for r in self._results.values() if r.strategy_id == strategy_id]
        return results[-1] if results else None

    async def health_check(self) -> dict[str, Any]:
        """Check adapter health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "checks_performed": len(self._results),
        }
