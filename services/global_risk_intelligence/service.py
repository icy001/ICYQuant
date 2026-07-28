"""Global Risk Intelligence Service – unified risk API."""

from typing import Any, Optional

from .detector import SystemicRiskDetector, SystemicRiskAssessment
from .volatility import VolatilityRegimeEngine, RegimeResult
from .liquidity import LiquidityStressAnalyzer, LiquidityAssessment
from .black_swan import BlackSwanDetector, BlackSwanAssessment
from .contagion import ContagionEngine, ContagionResult
from .stress_test import PortfolioStressTest, StressTestResult
from .defense import AutoDefenseEngine, DefenseDecision
from .memory import RiskMemory, RiskEvent


class GlobalRiskIntelligenceService:
    """Unified service for global risk intelligence.

    Integrates systemic risk detection, volatility regime analysis,
    liquidity monitoring, black swan scanning, contagion modeling,
    stress testing, auto-defense, and risk memory into a single API.
    """

    def __init__(self) -> None:
        self.detector = SystemicRiskDetector()
        self.volatility = VolatilityRegimeEngine()
        self.liquidity = LiquidityStressAnalyzer()
        self.black_swan = BlackSwanDetector()
        self.contagion = ContagionEngine()
        self.stress_test = PortfolioStressTest()
        self.defense = AutoDefenseEngine()
        self.memory = RiskMemory()

    # ------------------------------------------------------------------
    # Systemic Risk
    # ------------------------------------------------------------------

    def detect_systemic_risk(self, market_data: Optional[dict[str, Any]] = None,
                             **kwargs: Any) -> SystemicRiskAssessment:
        """Run systemic risk detection across all domains."""
        return self.detector.detect(market_data, **kwargs)

    # ------------------------------------------------------------------
    # Volatility Regime
    # ------------------------------------------------------------------

    def classify_volatility(self, vix: float = 15.0,
                            vix_term: str = "contango",
                            vol_of_vol: float = 0.0) -> RegimeResult:
        """Classify volatility regime."""
        return self.volatility.classify(vix, vix_term, vol_of_vol)

    # ------------------------------------------------------------------
    # Liquidity
    # ------------------------------------------------------------------

    def analyze_liquidity(self, **kwargs: Any) -> LiquidityAssessment:
        """Analyze multi-channel liquidity conditions."""
        return self.liquidity.analyze(**kwargs)

    # ------------------------------------------------------------------
    # Black Swan
    # ------------------------------------------------------------------

    def detect_black_swan(self, market_stress: float = 0.1,
                          vix: float = 15.0,
                          credit_spread: float = 1.0,
                          geopolitical_tension: float = 0.0,
                          cyber_threat_level: float = 0.0,
                          ) -> BlackSwanAssessment:
        """Scan for black swan precursor signals."""
        return self.black_swan.detect(
            market_stress=market_stress,
            vix=vix,
            credit_spread=credit_spread,
            geopolitical_tension=geopolitical_tension,
            cyber_threat_level=cyber_threat_level,
        )

    # ------------------------------------------------------------------
    # Contagion
    # ------------------------------------------------------------------

    def analyze_contagion(self, source: str,
                          initial_shock: float = 0.5) -> ContagionResult:
        """Trace contagion propagation from a source."""
        return self.contagion.analyze(source, initial_shock)

    def analyze_contagion_multi(self,
                                sources: dict[str, float]) -> dict[str, ContagionResult]:
        """Analyze contagion from multiple sources."""
        return self.contagion.analyze_multi(sources)

    # ------------------------------------------------------------------
    # Stress Testing
    # ------------------------------------------------------------------

    def run_stress_test(self, scenario_name: str, **kwargs: Any) -> StressTestResult:
        """Run a named stress test scenario."""
        return self.stress_test.run(scenario_name, **kwargs)

    def run_all_stress_tests(self, **kwargs: Any) -> list[StressTestResult]:
        """Run all stress test scenarios."""
        return self.stress_test.run_all(**kwargs)

    # ------------------------------------------------------------------
    # Auto Defense
    # ------------------------------------------------------------------

    def decide_defense(self, risk_level: str = "normal",
                       systemic_score: float = 0.0,
                       vol_regime: str = "normal_vol",
                       liquidity_level: str = "normal",
                       current_drawdown: float = 0.0,
                       ) -> DefenseDecision:
        """Determine auto-defense actions."""
        return self.defense.decide(
            risk_level=risk_level,
            systemic_score=systemic_score,
            vol_regime=vol_regime,
            liquidity_level=liquidity_level,
            current_drawdown=current_drawdown,
        )

    # ------------------------------------------------------------------
    # Risk Memory
    # ------------------------------------------------------------------

    def record_risk_event(self, **kwargs: Any) -> RiskEvent:
        """Record a risk event to memory."""
        return self.memory.record(**kwargs)

    def get_risk_knowledge(self) -> dict[str, Any]:
        """Get risk knowledge base summary."""
        return self.memory.summary()

    # ------------------------------------------------------------------
    # Comprehensive Analysis
    # ------------------------------------------------------------------

    def comprehensive_risk_analysis(self,
                                     market_data: Optional[dict[str, Any]] = None,
                                     vix: float = 15.0,
                                     vix_term: str = "contango",
                                     funding_spread: float = 0.15,
                                     liquidity_data: Optional[dict[str, Any]] = None,
                                     contagion_source: Optional[str] = None,
                                     stress_scenario: str = "VIX 50",
                                     ) -> dict[str, Any]:
        """Run a comprehensive global risk analysis.

        Returns a complete risk dashboard aggregating all engines.
        """
        data = market_data or {}
        liq_data = liquidity_data or {}

        # Systemic risk
        systemic = self.detect_systemic_risk(data)

        # Volatility regime
        regime = self.classify_volatility(
            vix or data.get("vix", 15.0),
            vix_term,
        )

        # Liquidity
        liquidity = self.analyze_liquidity(
            funding_spread=funding_spread,
            **(liq_data),
        )

        # Black swan
        black_swan = self.detect_black_swan(
            vix=vix or data.get("vix", 15.0),
            market_stress=systemic.score,
        )

        # Contagion (if source specified)
        contagion = (
            self.analyze_contagion(contagion_source)
            if contagion_source else None
        )

        # Stress test
        stress = self.run_stress_test(stress_scenario)

        # Defense decision
        defense = self.decide_defense(
            risk_level=systemic.level.value,
            systemic_score=systemic.score,
            vol_regime=regime.regime.value,
            liquidity_level=liquidity.level.value,
        )

        # Aggregate: weighted risk score
        aggregate = (
            systemic.score * 0.30
            + (1.0 if regime.is_stressed else 0.0) * 0.25
            + liquidity.score * 0.20
            + black_swan.overall_probability * 2.0 * 0.15
            + (abs(stress.portfolio_loss) / 0.2) * 0.10
        )

        # Record event in memory
        self.record_risk_event(
            event_type="comprehensive_analysis",
            risk_level=systemic.level.value,
            systemic_score=systemic.score,
            volatility_regime=regime.regime.value,
            peak_drawdown=abs(stress.portfolio_loss),
            description=f"Comprehensive analysis: {systemic.description}",
        )

        return {
            "aggregate_risk_score": round(min(1.0, aggregate), 3),
            "systemic_risk": {
                "level": systemic.level.value,
                "score": systemic.score,
                "alarming_domains": systemic.alarming_domains,
                "description": systemic.description,
            },
            "volatility_regime": {
                "regime": regime.regime.value,
                "vix": regime.vix,
                "percentile": regime.vix_percentile,
                "stressed": regime.is_stressed,
                "size_multiplier": regime.size_multiplier,
            },
            "liquidity": {
                "level": liquidity.level.value,
                "score": liquidity.score,
                "stressed_channels": liquidity.stressed_channels,
                "position_cap": liquidity.position_size_cap,
            },
            "black_swan": {
                "probability": black_swan.overall_probability,
                "severity": black_swan.severity.value,
                "is_defcon": black_swan.is_defcon,
                "hedge_pct": black_swan.recommended_hedge,
            },
            "contagion": ({
                "source": contagion.source,
                "affected_nodes": contagion.affected_nodes,
                "systemic_impact": contagion.systemic_impact,
            } if contagion else None),
            "stress_test": {
                "scenario": stress.scenario,
                "loss": stress.portfolio_loss,
                "drawdown": stress.drawdown,
                "recovery_days": stress.recovery_estimate_days,
                "passed": stress.passed,
            },
            "defense_decision": {
                "level": defense.level.value,
                "actions": [o.action.value for o in defense.orders],
                "leverage_target": defense.leverage_target,
                "cash_target": defense.cash_pct_target,
                "description": defense.description,
            },
        }

    def clear_all(self) -> None:
        """Clear all engine histories."""
        self.detector.clear()
        self.volatility.clear()
        self.liquidity.clear()
        self.memory.clear()
