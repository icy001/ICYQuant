"""
Position Sizing Engine
======================
Converts trading signals into sized positions using configurable
sizing models (Kelly, Fixed Fractional, Volatility Target, Risk Parity).

Pipeline:
    Signal → Risk Budget → Sizing Model → Position Size
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SizingMethod(str, Enum):
    """Available position sizing methods."""

    KELLY = "kelly"
    FIXED_FRACTIONAL = "fixed_fractional"
    VOLATILITY = "volatility"
    RISK_PARITY = "risk_parity"
    EQUAL_WEIGHT = "equal_weight"
    CUSTOM = "custom"


@dataclass
class SizingRequest:
    """Input to the position sizing engine."""

    signal_id: str = ""
    strategy_id: str = ""
    instrument: str = ""
    direction: str = ""
    confidence: float = 0.0
    signal_strength: float = 0.0

    # Risk parameters
    risk_budget: float = 0.0
    account_equity: float = 0.0
    max_position_pct: float = 0.0

    # Market parameters
    current_price: float = 0.0
    atr: float = 0.0
    annualized_volatility: float = 0.0

    # Strategy performance
    win_rate: float = 0.0
    payoff_ratio: float = 0.0

    # Method override
    method: Optional[SizingMethod] = None

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SizingResult:
    """Output of the position sizing engine."""

    signal_id: str = ""
    strategy_id: str = ""
    instrument: str = ""
    direction: str = ""

    # Sizing output
    position_size: float = 0.0  # In units/shares
    position_value: float = 0.0  # In account currency
    position_weight: float = 0.0  # As fraction of portfolio
    risk_exposure: float = 0.0  # Risk amount

    # Metadata
    method: SizingMethod = SizingMethod.FIXED_FRACTIONAL
    confidence: float = 0.0
    reason: str = ""

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "strategy_id": self.strategy_id,
            "instrument": self.instrument,
            "direction": self.direction,
            "position_size": self.position_size,
            "position_value": self.position_value,
            "position_weight": self.position_weight,
            "risk_exposure": self.risk_exposure,
            "method": self.method.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }


class PositionSizingEngine:
    """
    Position Sizing Engine.

    Transforms trading signals into sized positions using configurable
    sizing models. Supports Kelly, Fixed Fractional, Volatility Target,
    Risk Parity, and custom models.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._initialized = False

        # Default method
        self._default_method = SizingMethod(
            self._config.get("default_method", "fixed_fractional")
        )

        # Per-strategy method overrides
        self._strategy_methods: Dict[str, SizingMethod] = {}

        # Model registry
        self._models: Dict[SizingMethod, Any] = {}

        # Global constraints
        self._max_position_pct = self._config.get("max_position_pct", 0.20)
        self._min_position_pct = self._config.get("min_position_pct", 0.001)
        self._max_risk_per_trade_pct = self._config.get("max_risk_per_trade_pct", 0.02)

        # Metrics
        self._metrics: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return

        from services.strategy.portfolio.kelly_sizing import KellySizingModel
        from services.strategy.portfolio.fixed_fractional import FixedFractionalModel
        from services.strategy.portfolio.volatility_sizing import VolatilitySizingModel
        from services.strategy.portfolio.risk_parity_sizing import RiskParitySizingModel

        self._models = {
            SizingMethod.KELLY: KellySizingModel(self._config.get("kelly", {})),
            SizingMethod.FIXED_FRACTIONAL: FixedFractionalModel(self._config.get("fixed_fractional", {})),
            SizingMethod.VOLATILITY: VolatilitySizingModel(self._config.get("volatility", {})),
            SizingMethod.RISK_PARITY: RiskParitySizingModel(self._config.get("risk_parity", {})),
        }

        # Initialize all models
        for model in self._models.values():
            if hasattr(model, "initialize"):
                await model.initialize()

        # Load per-strategy overrides
        overrides = self._config.get("strategy_methods", {})
        for sid, method_name in overrides.items():
            try:
                self._strategy_methods[sid] = SizingMethod(method_name)
            except ValueError:
                logger.warning("Invalid sizing method '%s' for strategy %s", method_name, sid)

        self._initialized = True
        logger.info(
            "PositionSizingEngine initialized (default=%s, models=%d)",
            self._default_method.value,
            len(self._models),
        )

    async def shutdown(self) -> None:
        for model in self._models.values():
            if hasattr(model, "shutdown"):
                await model.shutdown()
        self._models.clear()
        self._strategy_methods.clear()
        self._initialized = False
        logger.info("PositionSizingEngine shut down")

    # ------------------------------------------------------------------
    # Sizing
    # ------------------------------------------------------------------

    def _resolve_method(self, request: SizingRequest) -> SizingMethod:
        """Resolve which sizing method to use for a given request."""
        if request.method:
            return request.method
        if request.strategy_id in self._strategy_methods:
            return self._strategy_methods[request.strategy_id]
        return self._default_method

    def _build_request_dict(self, request: SizingRequest) -> Dict[str, Any]:
        """Convert SizingRequest to a dict for model consumption."""
        return {
            "signal_id": request.signal_id,
            "strategy_id": request.strategy_id,
            "instrument": request.instrument,
            "direction": request.direction,
            "confidence": request.confidence,
            "signal_strength": request.signal_strength,
            "risk_budget": request.risk_budget,
            "account_equity": request.account_equity,
            "max_position_pct": request.max_position_pct or self._max_position_pct,
            "current_price": request.current_price,
            "atr": request.atr,
            "annualized_volatility": request.annualized_volatility,
            "win_rate": request.win_rate,
            "payoff_ratio": request.payoff_ratio,
            "max_risk_per_trade_pct": self._max_risk_per_trade_pct,
            "metadata": request.metadata,
        }

    def _apply_global_constraints(self, result: SizingResult, request: SizingRequest) -> SizingResult:
        """Apply global position size constraints."""
        max_pct = request.max_position_pct or self._max_position_pct
        min_pct = self._min_position_pct
        equity = request.account_equity or 1.0

        # Cap at max position percentage
        max_value = equity * max_pct
        if result.position_value > max_value:
            scale = max_value / result.position_value if result.position_value > 0 else 1.0
            result.position_value = max_value
            result.position_size *= scale
            result.position_weight = max_pct
            result.reason += f" (capped at {max_pct:.1%})"

        # Floor at min position percentage
        min_value = equity * min_pct
        if result.position_value < min_value and result.position_value > 0:
            logger.debug(
                "Position %s below minimum (%.2f < %.2f), setting to 0",
                request.instrument,
                result.position_value,
                min_value,
            )
            result.position_size = 0.0
            result.position_value = 0.0
            result.position_weight = 0.0

        return result

    async def size_single(self, request: SizingRequest) -> SizingResult:
        """Size a single position from a signal request."""
        if not self._initialized:
            await self.initialize()

        method = self._resolve_method(request)
        model = self._models.get(method)

        if model is None:
            logger.warning("No model for method %s, falling back to fixed_fractional", method)
            method = SizingMethod.FIXED_FRACTIONAL
            model = self._models[method]

        params = self._build_request_dict(request)

        try:
            raw_result = await model.compute(params)
        except Exception as exc:
            logger.error("Sizing failed for %s with %s: %s", request.instrument, method.value, exc)
            # Return zero-sized result on error
            return SizingResult(
                signal_id=request.signal_id,
                strategy_id=request.strategy_id,
                instrument=request.instrument,
                direction=request.direction,
                position_size=0.0,
                position_value=0.0,
                position_weight=0.0,
                method=method,
                confidence=request.confidence,
                reason=f"Error: {exc}",
            )

        result = SizingResult(
            signal_id=request.signal_id,
            strategy_id=request.strategy_id,
            instrument=request.instrument,
            direction=request.direction,
            position_size=raw_result.get("position_size", 0.0),
            position_value=raw_result.get("position_value", 0.0),
            position_weight=raw_result.get("position_weight", 0.0),
            risk_exposure=raw_result.get("risk_exposure", 0.0),
            method=method,
            confidence=request.confidence,
            reason=raw_result.get("reason", f"Sized via {method.value}"),
            metadata=raw_result.get("metadata", {}),
        )

        result = self._apply_global_constraints(result, request)

        self._metrics["sized_total"] = self._metrics.get("sized_total", 0) + 1
        self._metrics[f"sized_{method.value}"] = self._metrics.get(f"sized_{method.value}", 0) + 1

        return result

    async def size_positions(
        self,
        signals: List[Any],
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Size multiple positions from a list of signals.

        Args:
            signals: List of signals (from Signal Engine).
            portfolio_state: Current portfolio state.

        Returns:
            List of sized position dicts.
        """
        if not self._initialized:
            await self.initialize()

        # Convert signals to SizingRequest objects
        requests = []
        for sig in signals:
            sig_dict = sig if isinstance(sig, dict) else sig.to_dict() if hasattr(sig, "to_dict") else {}
            req = SizingRequest(
                signal_id=sig_dict.get("signal_id", ""),
                strategy_id=sig_dict.get("strategy_id", ""),
                instrument=sig_dict.get("instrument", ""),
                direction=sig_dict.get("direction", ""),
                confidence=sig_dict.get("confidence", 0.0),
                signal_strength=sig_dict.get("strength", sig_dict.get("signal_strength", 0.0)),
                risk_budget=sig_dict.get("risk_budget", 0.0),
                account_equity=(portfolio_state or {}).get("equity", sig_dict.get("account_equity", 100000.0)),
                max_position_pct=sig_dict.get("max_position_pct", 0.0),
                current_price=sig_dict.get("current_price", 0.0),
                atr=sig_dict.get("atr", 0.0),
                annualized_volatility=sig_dict.get("annualized_volatility", 0.0),
                win_rate=sig_dict.get("win_rate", 0.0),
                payoff_ratio=sig_dict.get("payoff_ratio", 0.0),
                metadata=sig_dict.get("metadata", {}),
            )
            requests.append(req)

        # Size all in parallel
        results = await asyncio.gather(
            *[self.size_single(req) for req in requests],
            return_exceptions=True,
        )

        # Filter errors
        sized = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Sizing failed for signal %d: %s", i, result)
                continue
            sized.append(result.to_dict())

        logger.info("Sized %d/%d signals successfully", len(sized), len(signals))
        return sized

    # ------------------------------------------------------------------
    # Model Management
    # ------------------------------------------------------------------

    def register_model(self, method: SizingMethod, model: Any) -> None:
        """Register a custom sizing model."""
        self._models[method] = model
        logger.info("Sizing model registered: %s", method.value)

    def set_strategy_method(self, strategy_id: str, method: SizingMethod) -> None:
        """Set the sizing method for a specific strategy."""
        self._strategy_methods[strategy_id] = method

    def get_method_for_strategy(self, strategy_id: str) -> SizingMethod:
        return self._strategy_methods.get(strategy_id, self._default_method)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, int]:
        return dict(self._metrics)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
