"""Execution Intelligence Service – unified API for smart order execution."""

from typing import Any, Dict, List, Optional

from .order import ExecutionOrder
from .plan import ExecutionPlan
from .routing import SmartRoutingEngine, Venue
from .slippage import SlippagePredictor, SlippageEstimate
from .impact import MarketImpactModel, ImpactEstimate
from .strategy import ExecutionStrategyEngine
from .tca import TransactionCostAnalyzer, TCAResult


class ExecutionIntelligenceService:
    """Unified service for AI-powered execution intelligence.

    Integrates order planning, smart routing, slippage prediction,
    market impact analysis, execution strategy selection, and
    transaction cost analysis into a single execution pipeline.

    Typical workflow:
        order → plan → route → predict costs → execute → analyze
    """

    def __init__(
        self,
        router: Optional[SmartRoutingEngine] = None,
        slippage: Optional[SlippagePredictor] = None,
        impact: Optional[MarketImpactModel] = None,
        strategy: Optional[ExecutionStrategyEngine] = None,
        tca: Optional[TransactionCostAnalyzer] = None,
    ):
        self._router = router or SmartRoutingEngine()
        self._slippage = slippage or SlippagePredictor()
        self._impact = impact or MarketImpactModel()
        self._strategy = strategy or ExecutionStrategyEngine()
        self._tca = tca or TransactionCostAnalyzer()

    # ------------------------------------------------------------------
    # Order Planning
    # ------------------------------------------------------------------

    def create_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        urgency: str = "normal",
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
        portfolio_id: str = "",
        strategy_id: str = "",
        reason: str = "",
    ) -> ExecutionOrder:
        """Create a new execution order."""
        return ExecutionOrder(
            symbol=symbol,
            side=side.upper(),
            quantity=quantity,
            urgency=urgency,
            order_type=order_type,
            limit_price=limit_price,
            portfolio_id=portfolio_id,
            strategy_id=strategy_id,
            reason=reason,
        )

    def plan_order(
        self,
        order: ExecutionOrder,
        avg_daily_volume: int = 1_000_000,
        strategy: Optional[str] = None,
        duration: Optional[int] = None,
        slices: Optional[int] = None,
    ) -> ExecutionPlan:
        """Generate an execution plan for an order."""
        return self._strategy.create_plan(
            order=order,
            strategy=strategy,
            duration=duration,
            avg_daily_volume=avg_daily_volume,
            slices=slices,
        )

    # ------------------------------------------------------------------
    # Smart Routing
    # ------------------------------------------------------------------

    def route(self, order: ExecutionOrder) -> dict:
        """Route an order to the optimal venue."""
        return self._router.route(order)

    def execute_plan(self, order: ExecutionOrder) -> dict:
        """Legacy interface: route an order (backward compat)."""
        return self._router.route(order)

    def list_venues(self) -> List[dict]:
        """List all available trading venues."""
        return self._router.list_venues()

    def add_venue(self, name: str, liquidity_score: float = 1.0,
                  spread_bps: float = 0.0, fee_bps: float = 0.0,
                  latency_ms: float = 0.0, market_depth: float = 1.0) -> None:
        """Register a new trading venue."""
        self._router.add_venue(Venue(
            name=name,
            liquidity_score=liquidity_score,
            spread_bps=spread_bps,
            fee_bps=fee_bps,
            latency_ms=latency_ms,
            market_depth=market_depth,
        ))

    # ------------------------------------------------------------------
    # Slippage Prediction
    # ------------------------------------------------------------------

    def predict_slippage(
        self,
        order: ExecutionOrder,
        market_volume: int = 100_000,
        spread_bps: Optional[float] = None,
    ) -> float:
        """Predict slippage in basis points."""
        return self._slippage.predict(order, market_volume, spread_bps)

    def predict_slippage_detailed(
        self,
        order: ExecutionOrder,
        market_volume: int = 100_000,
        spread_bps: Optional[float] = None,
    ) -> SlippageEstimate:
        """Predict slippage with factor breakdown."""
        return self._slippage.predict_detailed(order, market_volume, spread_bps)

    def expected_fill_price(
        self,
        order: ExecutionOrder,
        mid_price: float,
        market_volume: int = 100_000,
    ) -> float:
        """Compute expected fill price."""
        return self._slippage.expected_fill_price(order, mid_price, market_volume)

    # ------------------------------------------------------------------
    # Market Impact
    # ------------------------------------------------------------------

    def estimate_impact(
        self,
        quantity: int,
        avg_daily_volume: int = 1_000_000,
        price: float = 100.0,
    ) -> float:
        """Estimate market impact in basis points."""
        return self._impact.estimate(quantity, avg_daily_volume, price)

    def estimate_impact_detailed(
        self,
        quantity: int,
        avg_daily_volume: int = 1_000_000,
        price: float = 100.0,
    ) -> ImpactEstimate:
        """Detailed market impact estimate."""
        return self._impact.estimate_detailed(quantity, avg_daily_volume, price)

    def estimate_impact_for_order(
        self,
        order: ExecutionOrder,
        avg_daily_volume: int = 1_000_000,
        price: float = 100.0,
    ) -> ImpactEstimate:
        """Estimate market impact for an order."""
        return self._impact.estimate_for_order(order, avg_daily_volume, price)

    def optimal_slices(
        self,
        quantity: int,
        avg_daily_volume: int = 1_000_000,
        price: float = 100.0,
        max_impact_per_slice_bps: float = 2.0,
    ) -> int:
        """Recommend optimal number of slices."""
        return self._impact.optimal_slice_count(
            quantity, avg_daily_volume, price, max_impact_per_slice_bps,
        )

    def cost_savings(
        self,
        quantity: int,
        avg_daily_volume: int = 1_000_000,
        price: float = 100.0,
    ) -> dict:
        """Estimate cost savings from smart execution."""
        return self._impact.cost_savings(quantity, avg_daily_volume, price)

    # ------------------------------------------------------------------
    # Strategy Selection
    # ------------------------------------------------------------------

    def choose_strategy(
        self,
        urgency: str = "normal",
        quantity: int = 1000,
        avg_daily_volume: int = 1_000_000,
    ) -> str:
        """Select the best execution strategy."""
        return self._strategy.choose(urgency, quantity, avg_daily_volume)

    def choose_strategy_for_order(
        self,
        order: ExecutionOrder,
        avg_daily_volume: int = 1_000_000,
    ) -> str:
        """Select strategy for an order."""
        return self._strategy.choose_for_order(order, avg_daily_volume)

    def list_strategies(self) -> List[dict]:
        """List all available execution strategies."""
        return self._strategy.list_strategies()

    # ------------------------------------------------------------------
    # Transaction Cost Analysis
    # ------------------------------------------------------------------

    def analyze_cost(
        self,
        expected: float,
        actual: float,
        symbol: str = "",
        side: str = "",
        quantity: int = 0,
        arrival_price: Optional[float] = None,
        vwap_price: Optional[float] = None,
        spread_bps: float = 2.0,
    ) -> float:
        """Analyze transaction cost in basis points."""
        return self._tca.analyze(
            expected, actual, symbol, side, quantity,
            arrival_price, vwap_price, spread_bps,
        )

    def analyze_cost_detailed(
        self,
        expected: float,
        actual: float,
        symbol: str = "",
        side: str = "",
        quantity: int = 0,
        arrival_price: Optional[float] = None,
        vwap_price: Optional[float] = None,
        spread_bps: float = 2.0,
    ) -> TCAResult:
        """Detailed transaction cost analysis."""
        return self._tca.analyze_detailed(
            expected, actual, symbol, side, quantity,
            arrival_price, vwap_price, spread_bps,
        )

    def analyze_batch(self, trades: List[dict]) -> List[TCAResult]:
        """Analyze a batch of trades."""
        return self._tca.analyze_batch(trades)

    def tca_summary(self, results: List[TCAResult]) -> dict:
        """Summarize TCA results."""
        return self._tca.summary(results)

    # ------------------------------------------------------------------
    # Full Execution Pipeline
    # ------------------------------------------------------------------

    def execute(
        self,
        symbol: str,
        side: str,
        quantity: int,
        urgency: str = "normal",
        mid_price: float = 100.0,
        avg_daily_volume: int = 1_000_000,
        portfolio_id: str = "",
        strategy_id: str = "",
        reason: str = "",
    ) -> dict:
        """Run the full execution intelligence pipeline.

        Creates an order, plans execution, routes to best venue,
        predicts costs, and returns a comprehensive execution brief.
        """
        # 1. Create order
        order = self.create_order(
            symbol=symbol,
            side=side,
            quantity=quantity,
            urgency=urgency,
            portfolio_id=portfolio_id,
            strategy_id=strategy_id,
            reason=reason,
        )

        # 2. Choose strategy
        strategy = self.choose_strategy_for_order(order, avg_daily_volume)

        # 3. Create execution plan
        plan = self.plan_order(order, avg_daily_volume, strategy=strategy)

        # 4. Route to best venue
        routing = self.route(order)

        # 5. Predict slippage
        slippage = self.predict_slippage_detailed(order)

        # 6. Estimate market impact
        impact = self.estimate_impact_for_order(order, avg_daily_volume, mid_price)

        # 7. Expected fill price
        fill_price = self.expected_fill_price(order, mid_price)

        return {
            "order": order.to_dict(),
            "strategy": strategy,
            "plan": plan.to_dict(),
            "routing": routing,
            "slippage": slippage.to_dict(),
            "impact": impact.to_dict(),
            "expected_fill_price": fill_price,
            "mid_price": mid_price,
        }
