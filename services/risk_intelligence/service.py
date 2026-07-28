"""Risk Intelligence Service – high-level API for AI risk management."""

from typing import Any, Dict, List, Optional

from .risk import RiskProfile, compute_risk_score
from .assessment import RiskAssessmentEngine
from .prediction import RiskPredictionEngine, RiskPrediction
from .stress_test import StressTestEngine, StressTestResult
from .scenario import ScenarioSimulator, Scenario
from .explanation import RiskExplanationEngine, RiskExplanation
from .systemic_risk import SystemicRiskDetector, SystemicRiskResult
from .crisis_warning import CrisisEarlyWarningSystem, CrisisWarningResult
from .volatility_regime import VolatilityRegimePredictor, RegimePrediction
from .defense import PortfolioDefenseAutomation, DefensePlan


class RiskIntelligenceService:
    """Unified service for AI-powered risk intelligence.

    Integrates assessment, prediction, stress testing, scenario
    simulation, risk explanation, systemic risk detection, crisis
    early warning, volatility regime prediction, and portfolio
    defense automation into a single API.
    """

    def __init__(
        self,
        assessment: Optional[RiskAssessmentEngine] = None,
        prediction: Optional[RiskPredictionEngine] = None,
        stress_test: Optional[StressTestEngine] = None,
        scenario: Optional[ScenarioSimulator] = None,
        explanation: Optional[RiskExplanationEngine] = None,
        systemic_risk: Optional[SystemicRiskDetector] = None,
        crisis_warning: Optional[CrisisEarlyWarningSystem] = None,
        volatility_regime: Optional[VolatilityRegimePredictor] = None,
        defense: Optional[PortfolioDefenseAutomation] = None,
    ):
        self.assessment = assessment or RiskAssessmentEngine()
        self.prediction = prediction or RiskPredictionEngine()
        self.stress_test = stress_test or StressTestEngine()
        self.scenario = scenario or ScenarioSimulator()
        self.explanation = explanation or RiskExplanationEngine()
        self.systemic_risk = systemic_risk or SystemicRiskDetector()
        self.crisis_warning = crisis_warning or CrisisEarlyWarningSystem()
        self.volatility_regime = volatility_regime or VolatilityRegimePredictor()
        self.defense = defense or PortfolioDefenseAutomation()

    # ------------------------------------------------------------------
    # Risk Assessment
    # ------------------------------------------------------------------

    def assess(
        self,
        portfolio_id: str,
        exposure: float,
        volatility: float = 0.0,
        drawdown: float = 0.0,
        concentration: float = 0.0,
        beta: float = 0.0,
        var_95: float = 0.0,
    ) -> RiskProfile:
        """Perform a full multi-dimensional risk assessment."""
        return self.assessment.evaluate(
            portfolio_id=portfolio_id,
            exposure=exposure,
            volatility=volatility,
            drawdown=drawdown,
            concentration=concentration,
            beta=beta,
            var_95=var_95,
        )

    # ------------------------------------------------------------------
    # Risk Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        current_volatility: float,
        vol_momentum: float = 0.0,
        correlation_regime: float = 0.0,
        market_stress: float = 0.0,
        horizon_days: Optional[int] = None,
    ) -> RiskPrediction:
        """Predict future risk levels."""
        return self.prediction.predict(
            current_volatility=current_volatility,
            vol_momentum=vol_momentum,
            correlation_regime=correlation_regime,
            market_stress=market_stress,
            horizon_days=horizon_days,
        )

    # ------------------------------------------------------------------
    # Stress Testing
    # ------------------------------------------------------------------

    def stress_test_scenario(
        self,
        scenario_name: str,
        portfolio_value: float = 1_000_000.0,
    ) -> Optional[StressTestResult]:
        """Run a stress test for a named scenario from the library."""
        sc = self.scenario.get_scenario(scenario_name)
        if sc is None:
            return None
        return self.stress_test.run(
            scenario=sc.name,
            portfolio_value=portfolio_value,
            price_shock=sc.price_shock,
            correlation_amplification=sc.correlation_amplification,
            liquidity_discount=sc.liquidity_discount,
        )

    def stress_test_all(
        self,
        portfolio_value: float = 1_000_000.0,
    ) -> List[StressTestResult]:
        """Run all predefined stress test scenarios."""
        results: List[StressTestResult] = []
        for sc in self.scenario.scenarios:
            result = self.stress_test.run(
                scenario=sc.name,
                portfolio_value=portfolio_value,
                price_shock=sc.price_shock,
                correlation_amplification=sc.correlation_amplification,
                liquidity_discount=sc.liquidity_discount,
            )
            results.append(result)
        return results

    def stress_test_summary(
        self, portfolio_value: float = 1_000_000.0
    ) -> dict:
        """Run all scenarios and return a summary."""
        results = self.stress_test_all(portfolio_value)
        return self.stress_test.summary(results)

    # ------------------------------------------------------------------
    # Risk Explanation
    # ------------------------------------------------------------------

    def explain(self, profile: RiskProfile) -> RiskExplanation:
        """Generate a human-readable explanation of a risk profile."""
        result = self.explanation.explain(profile)
        if isinstance(result, dict):
            return RiskExplanation(
                portfolio_id=profile.portfolio_id,
                risk_level=profile.level,
                score=profile.score,
                reason=result.get("reason", ""),
                factors=result.get("factors", []),
                recommendations=result.get("recommendations", []),
            )
        return result

    # ------------------------------------------------------------------
    # Systemic Risk
    # ------------------------------------------------------------------

    def detect_systemic_risk(
        self,
        avg_correlation: float = 0.2,
        credit_spread: float = 1.0,
        liquidity_stress: float = 0.1,
        vix: float = 15.0,
        dollar_trend: str = "stable",
        em_spread: float = 2.0,
    ) -> SystemicRiskResult:
        """Run systemic risk detection analysis."""
        return self.systemic_risk.assess(
            avg_correlation=avg_correlation,
            credit_spread=credit_spread,
            liquidity_stress=liquidity_stress,
            vix=vix,
            dollar_trend=dollar_trend,
            em_spread=em_spread,
        )

    def get_contagion_paths(self, source: str) -> list:
        """Get potential contagion paths from a source market."""
        return self.systemic_risk.get_contagion_paths(source)

    # ------------------------------------------------------------------
    # Crisis Early Warning
    # ------------------------------------------------------------------

    def analyze_crisis_warning(
        self,
        vix: float = 15.0,
        vix_change: float = 0.0,
        avg_correlation: float = 0.2,
        credit_spread: float = 1.0,
        credit_change: float = 0.0,
        liquidity_stress: float = 0.1,
        safe_haven_demand: float = 0.0,
        market_breadth: float = 0.5,
    ) -> CrisisWarningResult:
        """Run crisis early warning analysis."""
        return self.crisis_warning.analyze(
            vix=vix,
            vix_change=vix_change,
            avg_correlation=avg_correlation,
            credit_spread=credit_spread,
            credit_change=credit_change,
            liquidity_stress=liquidity_stress,
            safe_haven_demand=safe_haven_demand,
            market_breadth=market_breadth,
        )

    def quick_crisis_scan(self, vix: float = 0.0,
                          credit_spread: float = 0.0) -> dict:
        """Quick crisis scan for urgent warnings."""
        return self.crisis_warning.quick_scan(vix, credit_spread)

    # ------------------------------------------------------------------
    # Volatility Regime
    # ------------------------------------------------------------------

    def predict_volatility_regime(
        self,
        current_vol: float = 0.15,
        vix: float = 15.0,
        vix_1m: Optional[float] = None,
        vix_3m: Optional[float] = None,
        vix_6m: Optional[float] = None,
        vol_of_vol: float = 0.0,
        horizon_days: int = 21,
    ) -> RegimePrediction:
        """Predict future volatility regime."""
        return self.volatility_regime.predict(
            current_vol=current_vol,
            vix=vix,
            vix_1m=vix_1m,
            vix_3m=vix_3m,
            vix_6m=vix_6m,
            vol_of_vol=vol_of_vol,
            horizon_days=horizon_days,
        )

    def quick_regime_scan(self, vix: float = 15.0) -> dict:
        """Quick volatility regime scan."""
        return self.volatility_regime.quick_scan(vix)

    # ------------------------------------------------------------------
    # Portfolio Defense
    # ------------------------------------------------------------------

    def generate_defense_plan(
        self,
        systemic_risk_score: float = 0.0,
        crisis_alert: float = 0.0,
        volatility_regime: str = "normal",
        current_drawdown: float = 0.0,
        current_leverage: float = 1.0,
        concentration: float = 0.3,
        positions: Optional[dict] = None,
        correlations: Optional[dict] = None,
        risk_scenarios: Optional[list] = None,
    ) -> DefensePlan:
        """Generate a portfolio defense plan."""
        return self.defense.generate_plan(
            systemic_risk_score=systemic_risk_score,
            crisis_alert=crisis_alert,
            volatility_regime=volatility_regime,
            current_drawdown=current_drawdown,
            current_leverage=current_leverage,
            concentration=concentration,
            positions=positions,
            correlations=correlations,
            risk_scenarios=risk_scenarios,
        )

    def quick_defense_check(
        self,
        systemic_risk: float = 0.0,
        crisis_alert: float = 0.0,
        vol_regime: str = "normal",
        drawdown: float = 0.0,
    ) -> dict:
        """Quick check of required defense posture."""
        return self.defense.quick_defense_check(
            systemic_risk, crisis_alert, vol_regime, drawdown,
        )

    # ------------------------------------------------------------------
    # Comprehensive Analysis
    # ------------------------------------------------------------------

    def comprehensive_analysis(
        self,
        portfolio_id: str,
        exposure: float,
        volatility: float = 0.0,
        drawdown: float = 0.0,
        concentration: float = 0.0,
        beta: float = 0.0,
        var_95: float = 0.0,
        vol_momentum: float = 0.0,
        correlation_regime: float = 0.0,
        market_stress: float = 0.0,
    ) -> dict:
        """Run a comprehensive risk analysis: assess + predict + explain."""
        # Assessment
        profile = self.assess(portfolio_id, exposure, volatility,
                              drawdown, concentration, beta, var_95)

        # Prediction
        prediction = self.predict(volatility, vol_momentum,
                                  correlation_regime, market_stress)

        # Explanation
        explanation = self.explain(profile)

        # Stress test summary
        stress_summary = self.stress_test_summary()

        # Systemic risk
        systemic_result = self.detect_systemic_risk(
            avg_correlation=correlation_regime,
            vix=volatility * 100 if volatility > 0 else 15.0,
        )

        # Crisis warning
        crisis_result = self.analyze_crisis_warning(
            vix=volatility * 100 if volatility > 0 else 15.0,
            avg_correlation=correlation_regime,
        )

        # Volatility regime
        regime_result = self.predict_volatility_regime(
            current_vol=volatility if volatility > 0.01 else 0.15,
            vix=volatility * 100 if volatility > 0 else 15.0,
        )

        # Defense plan
        defense_plan = self.generate_defense_plan(
            systemic_risk_score=systemic_result.score,
            crisis_alert=crisis_result.composite_alert,
            volatility_regime=regime_result.current_regime.value,
            current_drawdown=drawdown,
            concentration=concentration,
        )

        return {
            "portfolio_id": portfolio_id,
            "risk_profile": profile.to_dict(),
            "risk_prediction": prediction.to_dict(),
            "risk_explanation": explanation.to_dict()
            if hasattr(explanation, "to_dict")
            else explanation,
            "stress_test_summary": stress_summary,
            "systemic_risk": {
                "level": systemic_result.level.value,
                "score": systemic_result.score,
                "description": systemic_result.description,
            },
            "crisis_warning": {
                "phase": crisis_result.current_phase.value,
                "composite_alert": crisis_result.composite_alert,
                "description": crisis_result.description,
            },
            "volatility_regime": {
                "current": regime_result.current_regime.value,
                "predicted": regime_result.predicted_regime.value,
                "transition": regime_result.transition.value,
                "description": regime_result.description,
            },
            "defense_plan": {
                "level": defense_plan.defense_level.value,
                "target_cash": defense_plan.target_cash,
                "hedge_budget": defense_plan.hedge_budget,
                "actions": len(defense_plan.actions),
                "description": defense_plan.description,
            },
        }

    # ------------------------------------------------------------------
    # Global Risk Scan
    # ------------------------------------------------------------------

    def global_risk_scan(
        self,
        vix: float = 15.0,
        credit_spread: float = 1.0,
        avg_correlation: float = 0.2,
        liquidity_stress: float = 0.1,
        dollar_trend: str = "stable",
        em_spread: float = 2.0,
        safe_haven_demand: float = 0.0,
        market_breadth: float = 0.5,
        vol_of_vol: float = 0.0,
    ) -> dict:
        """Run a complete global risk scan across all engines.

        Returns a unified risk dashboard with actionable intelligence
        from all four institutional risk engines.
        """
        # Systemic risk
        systemic = self.detect_systemic_risk(
            avg_correlation=avg_correlation,
            credit_spread=credit_spread,
            liquidity_stress=liquidity_stress,
            vix=vix,
            dollar_trend=dollar_trend,
            em_spread=em_spread,
        )

        # Crisis warning
        crisis = self.analyze_crisis_warning(
            vix=vix,
            avg_correlation=avg_correlation,
            credit_spread=credit_spread,
            liquidity_stress=liquidity_stress,
            safe_haven_demand=safe_haven_demand,
            market_breadth=market_breadth,
        )

        # Volatility regime
        regime = self.predict_volatility_regime(
            current_vol=vix / 100,
            vix=vix,
            vol_of_vol=vol_of_vol,
        )

        # Defense plan
        defense = self.generate_defense_plan(
            systemic_risk_score=systemic.score,
            crisis_alert=crisis.composite_alert,
            volatility_regime=regime.current_regime.value,
            concentration=0.3,
        )

        # Aggregate risk score
        aggregate = (
            systemic.score * 0.30
            + crisis.composite_alert * 0.30
            + (1 if regime.predicted_regime in
               ("high_vol", "extreme", "tail") else 0) * 0.20
            + (1 if defense.defense_level != "none" else 0) * 0.20
        )

        return {
            "aggregate_risk_score": round(aggregate, 3),
            "systemic_risk": {
                "level": systemic.level.value,
                "score": systemic.score,
                "early_warning": systemic.early_warning,
                "description": systemic.description,
                "contagion_channels": [
                    s.channel.value for s in systemic.critical_channels
                ],
            },
            "crisis_warning": {
                "phase": crisis.current_phase.value,
                "composite_alert": crisis.composite_alert,
                "should_defend": crisis.should_defend,
                "active_warnings": len(crisis.active_warnings),
                "urgent_warnings": len(crisis.urgent_warnings),
                "description": crisis.description,
            },
            "volatility_regime": {
                "current": regime.current_regime.value,
                "predicted": regime.predicted_regime.value,
                "transition": regime.transition.value,
                "shift_probability": regime.regime_shift_probability,
                "description": regime.description,
            },
            "defense_plan": {
                "level": defense.defense_level.value,
                "target_cash": defense.target_cash,
                "hedge_budget": defense.hedge_budget,
                "max_drawdown_limit": defense.max_drawdown_limit,
                "actions_count": len(defense.actions),
                "description": defense.description,
            },
            "summary": self._generate_global_summary(
                systemic, crisis, regime, defense, aggregate,
            ),
        }

    def _generate_global_summary(
        self,
        systemic: Any,
        crisis: Any,
        regime: Any,
        defense: Any,
        aggregate: float,
    ) -> str:
        """Generate a concise global risk summary."""
        if aggregate >= 0.7:
            urgency = "CRITICAL"
            action = "Immediate defensive action required"
        elif aggregate >= 0.5:
            urgency = "HIGH"
            action = "Strong defensive posture recommended"
        elif aggregate >= 0.3:
            urgency = "MODERATE"
            action = "Reduce risk and increase monitoring"
        elif aggregate >= 0.15:
            urgency = "ELEVATED"
            action = "Monitor closely, review hedges"
        else:
            urgency = "LOW"
            action = "Normal operations, maintain vigilance"

        return (
            f"[{urgency}] Global Risk: {aggregate:.2f}. "
            f"Systemic: {systemic.level.value}, "
            f"Crisis Phase: {crisis.current_phase.value}, "
            f"Vol Regime: {regime.current_regime.value}→{regime.predicted_regime.value}, "
            f"Defense: {defense.defense_level.value}. "
            f"{action}."
        )
