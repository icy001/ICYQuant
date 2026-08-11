"""Autonomy Orchestrator — Coordinates the autonomous research pipeline.

Orchestrates the full pipeline:
    Scan → Opportunity → Hypothesis → Research → Factor → Alpha → Strategy → Backtest
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .autonomous_platform import AutonomyConfig, AutonomyLevel

logger = logging.getLogger(__name__)


@dataclass
class CycleResult:
    """Result of one research cycle."""

    cycle_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    success: bool = False
    observations: int = 0
    opportunities_found: int = 0
    hypotheses_generated: int = 0
    hypotheses_validated: int = 0
    factors_found: int = 0
    alphas_found: int = 0
    strategies_generated: int = 0
    backtests_run: int = 0
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class AutonomyOrchestrator:
    """Autonomy Orchestrator — runs the discovery pipeline end-to-end.

    Pipeline steps:
    1. Scan market for anomalies and regime changes
    2. Detect research opportunities
    3. Generate hypotheses
    4. Validate hypotheses
    5. Plan research experiments
    6. Mine factors
    7. Discover alpha combinations
    8. Generate strategy candidates
    9. Run backtests
    10. Validate and register candidates
    """

    def __init__(self, config: "AutonomyConfig") -> None:
        self.config = config
        self._components: Dict[str, Any] = {}
        self._started = False
        self._cycles: List[CycleResult] = []

    async def start(self) -> None:
        self._started = True
        logger.info("Autonomy Orchestrator started")

    async def stop(self) -> None:
        self._started = False
        self._components.clear()
        logger.info("Autonomy Orchestrator stopped")

    def _get_components(self) -> Dict[str, Any]:
        """Lazy-load pipeline components."""
        if not self._components:
            from .market_scanner import MarketScanner
            from .anomaly_detector import AnomalyDetector
            from .regime_detector import RegimeDetector
            from .opportunity_detector import OpportunityDetector
            from .hypothesis_generator import HypothesisGenerator
            from .hypothesis_validator import HypothesisValidator
            from .factor_miner import FactorMiner
            from .alpha_discovery import AlphaDiscovery
            from .alpha_validator import AlphaValidator
            from .strategy_generator import StrategyGenerator
            from .strategy_validator import StrategyValidator
            from .backtest_orchestrator import BacktestOrchestrator

            self._components = {
                "scanner": MarketScanner(),
                "anomaly": AnomalyDetector(),
                "regime": RegimeDetector(),
                "opportunity": OpportunityDetector(),
                "hypothesis_generator": HypothesisGenerator(),
                "hypothesis_validator": HypothesisValidator(),
                "factor_miner": FactorMiner(),
                "alpha": AlphaDiscovery(),
                "alpha_validator": AlphaValidator(),
                "strategy_generator": StrategyGenerator(),
                "strategy_validator": StrategyValidator(),
                "backtest": BacktestOrchestrator(),
            }
        return self._components

    # ------------------------------------------------------------------
    # Full Research Cycle
    # ------------------------------------------------------------------

    async def run_cycle(
        self,
        universe: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run a complete autonomous research cycle.

        Returns:
            Dict with cycle results summary.
        """
        components = self._get_components()
        cycle_id = f"cycle_{time.monotonic_ns()}"
        result = CycleResult(cycle_id=cycle_id)

        try:
            # Step 1: Scan market
            scan_result = await components["scanner"].scan(universe=universe)
            observations = scan_result.get("observations", [])
            result.observations = len(observations)

            # Step 2: Detect anomalies
            anomaly_result = await components["anomaly"].detect(observations)
            anomalies = anomaly_result.get("anomalies", [])

            # Step 3: Detect regime
            regime_result = await components["regime"].detect(observations)
            regimes = regime_result.get("regimes", [])

            # Step 4: Detect opportunities (from observations, anomalies, regimes)
            opp_result = await components["opportunity"].detect(
                observations, anomalies=anomalies, regimes=regimes
            )
            opportunities = opp_result.get("opportunities", [])
            result.opportunities_found = len(opportunities)

            if not opportunities:
                result.success = True
                result.completed_at = datetime.now(timezone.utc)
                self._cycles.append(result)
                return self._cycle_to_dict(result)

            # Step 5: Generate hypotheses
            hyp_result = await components["hypothesis_generator"].generate(opportunities)
            hypotheses = hyp_result.get("hypotheses", [])
            result.hypotheses_generated = len(hypotheses)

            # Step 6: Validate hypotheses
            validated = []
            for hyp in hypotheses:
                validation = await components["hypothesis_validator"].validate(hyp)
                if validation.get("valid", False):
                    validated.append(hyp)
            result.hypotheses_validated = len(validated)

            if not validated:
                result.success = True
                result.completed_at = datetime.now(timezone.utc)
                self._cycles.append(result)
                return self._cycle_to_dict(result)

            # Step 7: Mine factors for each valid hypothesis
            all_factors = []
            for hyp in validated:
                if self.config.enable_auto_factor_discovery:
                    factor_result = await components["factor_miner"].mine(
                        hyp.get("hypothesis_id", "")
                    )
                    factors = factor_result.get("factors", [])
                    all_factors.extend(factors)
            result.factors_found = len(all_factors)

            # Step 8: Discover alpha from factors
            alpha_candidates = []
            if all_factors and self.config.enable_auto_alpha_discovery:
                alpha_result = await components["alpha"].discover(all_factors)
                alpha_candidates = alpha_result.get("alphas", [])
                result.alphas_found = len(alpha_candidates)

            # Step 9: Generate strategy candidates
            strategies = []
            if alpha_candidates and self.config.enable_auto_strategy_generation:
                strat_result = await components["strategy_generator"].generate(alpha_candidates)
                strategies = strat_result.get("strategies", [])
                result.strategies_generated = len(strategies)

            # Step 10: Run backtests for strategies
            for strat in strategies:
                bt_result = await components["backtest"].run(strat)
                result.backtests_run += 1

                # Validate strategy
                validation = await components["strategy_validator"].validate(strat, bt_result)
                if validation.get("valid", False):
                    result.candidates.append({
                        "strategy": strat,
                        "backtest": bt_result,
                        "validation": validation,
                    })

            result.success = True

        except Exception as exc:
            logger.error("Research cycle failed: %s", exc, exc_info=True)
            result.errors.append(str(exc))

        finally:
            result.completed_at = datetime.now(timezone.utc)
            self._cycles.append(result)

        return self._cycle_to_dict(result)

    # ------------------------------------------------------------------
    # Simplified Operations
    # ------------------------------------------------------------------

    async def scan(self) -> List[Dict[str, Any]]:
        """Quick market scan."""
        components = self._get_components()
        result = await components["scanner"].scan()
        return result.get("observations", [])

    async def discover_alpha(self, hypothesis_id: str) -> Dict[str, Any]:
        """Discover alpha for a hypothesis."""
        components = self._get_components()
        factors = await components["factor_miner"].mine(hypothesis_id)
        return await components["alpha"].discover(factors.get("factors", []))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cycle_to_dict(self, result: CycleResult) -> Dict[str, Any]:
        return {
            "cycle_id": result.cycle_id,
            "success": result.success,
            "observations": result.observations,
            "opportunities_found": result.opportunities_found,
            "hypotheses_generated": result.hypotheses_generated,
            "hypotheses_validated": result.hypotheses_validated,
            "factors_found": result.factors_found,
            "alphas_found": result.alphas_found,
            "strategies_generated": result.strategies_generated,
            "backtests_run": result.backtests_run,
            "candidates": result.candidates,
            "errors": result.errors,
        }

    async def health(self) -> Dict[str, Any]:
        return {
            "started": self._started,
            "total_cycles": len(self._cycles),
            "successful_cycles": sum(1 for c in self._cycles if c.success),
            "components": list(self._components.keys()),
        }
