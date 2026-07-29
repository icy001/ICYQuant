from typing import Any, Dict

from .trader_agent import AIExecutionTrader
from .planner import ExecutionPlanner
from .router import SmartOrderRouter
from .impact import MarketImpactPredictor
from .algo import ExecutionAlgorithmEngine
from .slippage import SlippageControlEngine
from .liquidity import LiquidityDetectionEngine
from .adaptive import AdaptiveExecutionEngine
from .quality import ExecutionQualityAnalyzer
from .memory import ExecutionMemory


class ExecutionIntelligenceService:
    """Execution Intelligence Service - orchestrates the full autonomous execution loop."""

    def __init__(self, trader):
        self.trader = trader
        self.planner = ExecutionPlanner()
        self.router = SmartOrderRouter()
        self.impact = MarketImpactPredictor()
        self.algo = ExecutionAlgorithmEngine()
        self.slippage = SlippageControlEngine()
        self.liquidity = LiquidityDetectionEngine()
        self.adaptive = AdaptiveExecutionEngine()
        self.quality = ExecutionQualityAnalyzer()
        self.memory = ExecutionMemory()

    def execute(self, order):
        """Execute an order through the full autonomous execution pipeline.

        Args:
            order: The order to execute.

        Returns:
            Dict containing execution result from the trader agent.
        """
        return self.trader.decide(order)

    def run_full_loop(self, order_intent) -> Dict[str, Any]:
        """Run the complete autonomous execution loop.

        Steps:
        1. Execution Trader decides
        2. Execution Planning
        3. Market Impact Prediction
        4. Smart Order Routing
        5. Execution via Algorithm
        6. Slippage Control
        7. Quality Analysis
        8. Memory Recording
        """
        # Step 1: AI Execution Trader decides
        decision = self.trader.decide(order_intent)

        # Step 2: Create execution plan
        plan = self.planner.plan(order_intent)

        # Step 3: Predict market impact
        impact_prediction = self.impact.predict(order_intent)

        # Step 4: Route order
        route = self.router.route(order_intent)

        # Step 5: Execute via algorithm
        algo_result = self.algo.execute(order_intent)

        # Step 6: Measure slippage
        slippage_result = self.slippage.measure(order_intent)

        # Step 7: Analyze quality
        quality_result = self.quality.analyze(order_intent)

        # Step 8: Save to memory
        self.memory.save(order_intent)

        return {
            "decision": decision,
            "plan": plan,
            "impact": impact_prediction,
            "route": route,
            "algorithm": algo_result,
            "slippage": slippage_result,
            "quality": quality_result,
            "status": "COMPLETED",
        }
