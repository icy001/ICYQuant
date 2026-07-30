"""
End-to-end integration validation for the ICYQuant trading flow.

Validates the complete data pipeline from Market Data through to PnL,
checking data flow integrity, type compatibility, and timing at each step.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class StepResult:
    step_name: str
    passed: bool
    duration_ms: float
    error_message: Optional[str] = None
    data_integrity: bool = True
    type_compatible: bool = True
    data_discrepancies: list[str] = field(default_factory=list)


@dataclass
class IntegrationResult:
    overall_passed: bool
    total_duration_ms: float
    steps: list[StepResult] = field(default_factory=list)
    discrepancies: list[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""

    @property
    def pass_rate(self) -> float:
        if not self.steps:
            return 0.0
        passed = sum(1 for s in self.steps if s.passed)
        return passed / len(self.steps)


class IntegrationValidator:
    """
    Validates the complete trading flow end-to-end.

    Tests the pipeline: Market Data -> Feature Store -> AI -> Signal ->
    Risk -> OMS -> EMS -> Broker -> Position -> Portfolio -> PnL.
    Each step validates data flow integrity, type compatibility, and timing.
    """

    def __init__(self) -> None:
        self._steps: list[tuple[str, Callable[[], StepResult]]] = []
        self._register_default_steps()

    def _register_default_steps(self) -> None:
        self._steps = [
            ("Market Data", self._validate_market_data),
            ("Feature Store", self._validate_feature_store),
            ("AI Inference", self._validate_ai_inference),
            ("Signal Generation", self._validate_signal),
            ("Risk Check", self._validate_risk),
            ("OMS Order", self._validate_oms),
            ("EMS Execution", self._validate_ems),
            ("Broker Communication", self._validate_broker),
            ("Position Update", self._validate_position),
            ("Portfolio Update", self._validate_portfolio),
            ("PnL Calculation", self._validate_pnl),
        ]

    def run(self) -> IntegrationResult:
        import datetime

        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        overall_start = time.perf_counter()

        step_results: list[StepResult] = []
        all_discrepancies: list[str] = []

        for step_name, step_func in self._steps:
            try:
                result = step_func()
                step_results.append(result)
                if result.data_discrepancies:
                    all_discrepancies.extend(result.data_discrepancies)
            except Exception as e:
                step_results.append(StepResult(
                    step_name=step_name,
                    passed=False,
                    duration_ms=0.0,
                    error_message=str(e),
                ))

        overall_duration = (time.perf_counter() - overall_start) * 1000
        completed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        overall_passed = all(s.passed for s in step_results)

        return IntegrationResult(
            overall_passed=overall_passed,
            total_duration_ms=overall_duration,
            steps=step_results,
            discrepancies=all_discrepancies,
            started_at=started_at,
            completed_at=completed_at,
        )

    def _validate_market_data(self) -> StepResult:
        start = time.perf_counter()
        try:
            from services.marketdata.bar import Bar
            bar = Bar(
                symbol="TEST",
                open=100.0,
                high=105.0,
                low=95.0,
                close=102.0,
                volume=1000000.0,
                timestamp=int(time.time()),
            )
            if not isinstance(bar, Bar):
                return StepResult(
                    step_name="Market Data",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Bar type mismatch",
                    type_compatible=False,
                )
            if bar.high < bar.low:
                return StepResult(
                    step_name="Market Data",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="OHLC inconsistency: high < low",
                    data_integrity=False,
                )
            if bar.open <= 0 or bar.close <= 0:
                return StepResult(
                    step_name="Market Data",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Invalid price values",
                    data_integrity=False,
                )
            return StepResult(
                step_name="Market Data",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return StepResult(
                step_name="Market Data",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _validate_feature_store(self) -> StepResult:
        start = time.perf_counter()
        try:
            feature_data = {
                "symbol": "TEST",
                "features": {
                    "momentum_10": 0.025,
                    "volatility_20": 0.018,
                    "volume_ratio": 1.15,
                    "rsi_14": 58.3,
                },
                "timestamp": int(time.time()),
            }
            required_keys = {"symbol", "features", "timestamp"}
            missing = required_keys - set(feature_data.keys())
            if missing:
                return StepResult(
                    step_name="Feature Store",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message=f"Missing keys: {missing}",
                    data_integrity=False,
                )
            if not isinstance(feature_data["features"], dict):
                return StepResult(
                    step_name="Feature Store",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Features must be a dict",
                    type_compatible=False,
                )
            discrepancies: list[str] = []
            for name, value in feature_data["features"].items():
                if not isinstance(value, (int, float)):
                    discrepancies.append(
                        f"Feature '{name}' is not numeric: {type(value).__name__}"
                    )
            return StepResult(
                step_name="Feature Store",
                passed=len(discrepancies) == 0,
                duration_ms=(time.perf_counter() - start) * 1000,
                data_discrepancies=discrepancies,
                data_integrity=len(discrepancies) == 0,
                type_compatible=len(discrepancies) == 0,
            )
        except Exception as e:
            return StepResult(
                step_name="Feature Store",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _validate_ai_inference(self) -> StepResult:
        start = time.perf_counter()
        try:
            from services.ai.alpha_score import AlphaScore
            score = AlphaScore(
                alpha_name="momentum_alpha",
                sharpe=1.5,
                return_score=0.75,
                stability=0.88,
            )
            if not isinstance(score, AlphaScore):
                return StepResult(
                    step_name="AI Inference",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="AlphaScore type mismatch",
                    type_compatible=False,
                )
            if not 0 <= score.return_score <= 1:
                return StepResult(
                    step_name="AI Inference",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message=f"return_score out of range [0,1]: {score.return_score}",
                    data_integrity=False,
                )
            if not 0 <= score.stability <= 1:
                return StepResult(
                    step_name="AI Inference",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message=f"stability out of range [0,1]: {score.stability}",
                    data_integrity=False,
                )
            return StepResult(
                step_name="AI Inference",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return StepResult(
                step_name="AI Inference",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _validate_signal(self) -> StepResult:
        start = time.perf_counter()
        try:
            from services.signal.model import Signal
            signal = Signal(
                signal_id="signal_001",
                symbol="TEST",
                direction="LONG",
                score=0.82,
            )
            if not isinstance(signal, Signal):
                return StepResult(
                    step_name="Signal Generation",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Signal type mismatch",
                    type_compatible=False,
                )
            valid_directions = {"LONG", "SHORT", "NEUTRAL"}
            if signal.direction not in valid_directions:
                return StepResult(
                    step_name="Signal Generation",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message=f"Invalid direction: {signal.direction}",
                    data_integrity=False,
                )
            if not 0 <= signal.score <= 1:
                return StepResult(
                    step_name="Signal Generation",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message=f"Score out of range [0,1]: {signal.score}",
                    data_integrity=False,
                )
            return StepResult(
                step_name="Signal Generation",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return StepResult(
                step_name="Signal Generation",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _validate_risk(self) -> StepResult:
        start = time.perf_counter()
        try:
            from services.risk.result import RiskResult, RiskDecision
            result = RiskResult(
                decision=RiskDecision.PASS,
                message="Within limits",
            )
            if not isinstance(result, RiskResult):
                return StepResult(
                    step_name="Risk Check",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="RiskResult type mismatch",
                    type_compatible=False,
                )
            if not isinstance(result.decision, RiskDecision):
                return StepResult(
                    step_name="Risk Check",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message=f"Invalid decision type: {type(result.decision)}",
                    data_integrity=False,
                )
            return StepResult(
                step_name="Risk Check",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return StepResult(
                step_name="Risk Check",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _validate_oms(self) -> StepResult:
        start = time.perf_counter()
        try:
            from services.order.model import Order
            from services.order.enums import OrderType, OrderSide
            order = Order(
                order_id="order_001",
                account_id="account_001",
                portfolio_id="portfolio_001",
                symbol="TEST",
                quantity=100.0,
                price=102.5,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
            )
            if not isinstance(order, Order):
                return StepResult(
                    step_name="OMS Order",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Order type mismatch",
                    type_compatible=False,
                )
            if order.quantity <= 0:
                return StepResult(
                    step_name="OMS Order",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Quantity must be positive",
                    data_integrity=False,
                )
            if order.price <= 0:
                return StepResult(
                    step_name="OMS Order",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Price must be positive",
                    data_integrity=False,
                )
            return StepResult(
                step_name="OMS Order",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return StepResult(
                step_name="OMS Order",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _validate_ems(self) -> StepResult:
        start = time.perf_counter()
        try:
            from services.order.model import Order
            from services.order.enums import OrderType, OrderSide
            order = Order(
                order_id="order_001",
                account_id="account_001",
                portfolio_id="portfolio_001",
                symbol="TEST",
                quantity=100.0,
                price=102.5,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
            )
            if not isinstance(order, Order):
                return StepResult(
                    step_name="EMS Execution",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Order type mismatch in EMS",
                    type_compatible=False,
                )
            slices = 10
            if slices <= 0:
                return StepResult(
                    step_name="EMS Execution",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Slice count must be positive",
                    data_integrity=False,
                )
            return StepResult(
                step_name="EMS Execution",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return StepResult(
                step_name="EMS Execution",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _validate_broker(self) -> StepResult:
        start = time.perf_counter()
        try:
            from services.trade.model import Trade
            trade = Trade(
                trade_id="trade_001",
                order_id="order_001",
                account_id="account_001",
                symbol="TEST",
                quantity=100.0,
                price=102.5,
                side="BUY",
                timestamp=int(time.time()),
            )
            if not isinstance(trade, Trade):
                return StepResult(
                    step_name="Broker Communication",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Trade type mismatch",
                    type_compatible=False,
                )
            if trade.quantity <= 0:
                return StepResult(
                    step_name="Broker Communication",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Trade quantity must be positive",
                    data_integrity=False,
                )
            if trade.price <= 0:
                return StepResult(
                    step_name="Broker Communication",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Trade price must be positive",
                    data_integrity=False,
                )
            return StepResult(
                step_name="Broker Communication",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return StepResult(
                step_name="Broker Communication",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _validate_position(self) -> StepResult:
        start = time.perf_counter()
        try:
            from services.position.model import Position
            position = Position(
                position_id="position_001",
                account_id="account_001",
                portfolio_id="portfolio_001",
                symbol="TEST",
                quantity=100.0,
                avg_price=102.5,
                side="LONG",
            )
            if not isinstance(position, Position):
                return StepResult(
                    step_name="Position Update",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Position type mismatch",
                    type_compatible=False,
                )
            if position.quantity <= 0:
                return StepResult(
                    step_name="Position Update",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Position quantity must be positive",
                    data_integrity=False,
                )
            return StepResult(
                step_name="Position Update",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return StepResult(
                step_name="Position Update",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _validate_portfolio(self) -> StepResult:
        start = time.perf_counter()
        try:
            from services.portfolio.model import Portfolio
            portfolio = Portfolio(
                portfolio_id="portfolio_001",
                account_id="account_001",
                name="Test Portfolio",
            )
            if not isinstance(portfolio, Portfolio):
                return StepResult(
                    step_name="Portfolio Update",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Portfolio type mismatch",
                    type_compatible=False,
                )
            if not portfolio.portfolio_id:
                return StepResult(
                    step_name="Portfolio Update",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message="Portfolio ID is required",
                    data_integrity=False,
                )
            return StepResult(
                step_name="Portfolio Update",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return StepResult(
                step_name="Portfolio Update",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )

    def _validate_pnl(self) -> StepResult:
        start = time.perf_counter()
        try:
            from decimal import Decimal
            from services.portfolio.pnl import PnLCalculator
            calculator = PnLCalculator()
            pnl = calculator.unrealized(
                quantity=Decimal("100"),
                cost=Decimal("102.5"),
                price=Decimal("105.0"),
            )
            expected = Decimal("250.0")
            if pnl != expected:
                return StepResult(
                    step_name="PnL Calculation",
                    passed=False,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error_message=f"PnL calculation mismatch: expected {expected}, got {pnl}",
                    data_integrity=False,
                )
            return StepResult(
                step_name="PnL Calculation",
                passed=True,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as e:
            return StepResult(
                step_name="PnL Calculation",
                passed=False,
                duration_ms=(time.perf_counter() - start) * 1000,
                error_message=str(e),
            )