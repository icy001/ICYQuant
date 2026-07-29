from typing import Any, Dict

from .deployment import CapitalDeploymentAgent
from .optimizer import CapitalAllocationOptimizer
from .ranking import OpportunityRankingEngine
from .rotation import CapitalRotationEngine
from .exposure import DynamicExposureControl
from .cash import CashManagementAI
from .liquidity import LiquidityOptimizationEngine
from .efficiency import CapitalEfficiencyAnalyzer
from .stress import CapitalStressTester
from .memory import CapitalMemory


class CapitalAllocationService:
    """Capital Allocation Service - orchestrates the full autonomous capital management loop."""

    def __init__(self, agent):
        self.agent = agent
        self.optimizer = CapitalAllocationOptimizer()
        self.ranking_engine = OpportunityRankingEngine()
        self.rotation_engine = CapitalRotationEngine()
        self.exposure_control = DynamicExposureControl()
        self.cash_manager = CashManagementAI()
        self.liquidity_engine = LiquidityOptimizationEngine()
        self.efficiency_analyzer = CapitalEfficiencyAnalyzer()
        self.stress_tester = CapitalStressTester()
        self.memory = CapitalMemory()

    def allocate(self, decision):
        """Allocate capital based on an investment decision.

        Args:
            decision: The investment decision to act upon.

        Returns:
            Dict containing capital plan.
        """
        return self.agent.deploy(decision)

    def run_full_loop(self, decision, portfolio_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Run the complete autonomous capital allocation loop.

        Steps:
        1. Capital Deployment Plan
        2. Allocation Optimization
        3. Opportunity Ranking
        4. Capital Rotation Check
        5. Exposure Adjustment
        6. Cash Management
        7. Liquidity Analysis
        8. Efficiency Analysis
        9. Stress Testing
        10. Memory Recording
        """
        if portfolio_data is None:
            portfolio_data = {}

        # Step 1: Generate capital deployment plan
        capital_plan = self.agent.deploy(decision)

        # Step 2: Optimize allocation
        positions = portfolio_data.get("positions", [])
        allocation = self.optimizer.optimize({
            "positions": positions,
            "total_capital": portfolio_data.get("total_capital", 1000000.0),
            "objective": portfolio_data.get("objective", "MAX_SHARPE"),
        })

        # Step 3: Rank opportunities
        ranking = self.ranking_engine.rank(positions if positions else [decision])

        # Step 4: Capital rotation
        rotation = self.rotation_engine.rotate({
            "positions": positions,
        })

        # Step 5: Dynamic exposure control
        exposure = self.exposure_control.adjust({
            "current_exposure": portfolio_data.get("current_exposure", 0.6),
            "market_regime": portfolio_data.get("market_regime", "NORMAL"),
            "volatility": portfolio_data.get("volatility", 0.15),
            "risk_level": portfolio_data.get("risk_level", "MEDIUM"),
            "conviction": portfolio_data.get("conviction", 50),
        })

        # Step 6: Cash management
        cash = self.cash_manager.manage({
            "total_cash": portfolio_data.get("total_cash", 100000.0),
            "total_aum": portfolio_data.get("total_aum", 1000000.0),
            "market_regime": portfolio_data.get("market_regime", "NORMAL"),
        })

        # Step 7: Liquidity analysis
        liquidity = self.liquidity_engine.analyze(positions if positions else [decision])

        # Step 8: Efficiency analysis
        efficiency = self.efficiency_analyzer.analyze({
            "total_capital": portfolio_data.get("total_capital", portfolio_data.get("total_aum", 1000000.0)),
            "deployed_capital": portfolio_data.get("deployed_capital", 800000.0),
            "return": portfolio_data.get("return", 0.12),
        })

        # Step 9: Stress testing
        stress = self.stress_tester.simulate({
            "total_capital": portfolio_data.get("total_capital", portfolio_data.get("total_aum", 1000000.0)),
            "current_exposure": portfolio_data.get("current_exposure", 0.6),
            "leverage": portfolio_data.get("leverage", 1.0),
            "cash_ratio": portfolio_data.get("cash_ratio", 0.10),
        })

        # Step 10: Save to memory
        self.memory.save(capital_plan)

        return {
            "capital_plan": capital_plan,
            "allocation": allocation,
            "ranking": ranking,
            "rotation": rotation,
            "exposure": exposure,
            "cash": cash,
            "liquidity": liquidity,
            "efficiency": efficiency,
            "stress": stress,
            "status": "COMPLETED",
        }
