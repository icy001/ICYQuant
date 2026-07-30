from typing import Dict, List, Optional

from .risk_predictor import RiskPredictor, RiskPrediction
from .market_regime import MarketRegimeDetector, MarketRegime
from .black_swan import BlackSwanDetector, BlackSwanEvent
from .stress_testing import StressTestingEngine, StressTestResult
from .scenario_engine import ScenarioEngine, ScenarioResult
from .portfolio_risk import PortfolioRiskEngine, PortfolioRisk
from .exposure_engine import ExposureEngine, ExposureReport
from .position_sizer import DynamicPositionSizer, PositionSize
from .limit_manager import AdaptiveLimitManager, RiskLimitConfig
from .adaptive_controller import AdaptiveController, AdaptiveControlResult


class RiskIntelligenceService:
    def __init__(self):
        self.risk_predictor = RiskPredictor()
        self.regime_detector = MarketRegimeDetector()
        self.bs_detector = BlackSwanDetector()
        self.stress_engine = StressTestingEngine()
        self.scenario_engine = ScenarioEngine()
        self.portfolio_engine = PortfolioRiskEngine()
        self.exposure_engine = ExposureEngine()
        self.position_sizer = DynamicPositionSizer()
        self.limit_manager = AdaptiveLimitManager()
        self.adaptive_controller = AdaptiveController()

    def get_risk_score(
        self,
        volatility: float = 0.2,
        liquidity: float = 0.8,
        credit_spread: float = 0.05,
        var_95: float = 0.02,
    ) -> RiskPrediction:
        return self.risk_predictor.predict(
            volatility=volatility,
            liquidity=liquidity,
            credit_spread=credit_spread,
            var_95=var_95,
        )

    def detect_market_regime(
        self,
        trend: float = 0.01,
        volatility: float = 0.15,
        volume_ratio: float = 1.0,
        spread: float = 0.0005,
    ) -> MarketRegime:
        return self.regime_detector.detect(
            trend=trend,
            volatility=volatility,
            volume_ratio=volume_ratio,
            spread=spread,
        )

    def detect_black_swan(
        self,
        index_decline: float = 0.0,
        vix_change: float = 0.0,
        volume_surge: float = 1.0,
        bid_ask_spread: float = 0.0005,
    ) -> BlackSwanEvent:
        return self.bs_detector.detect(
            index_decline=index_decline,
            vix_change=vix_change,
            volume_surge=volume_surge,
            bid_ask_spread=bid_ask_spread,
        )

    def run_stress_test(
        self,
        scenario_name: str = "market_crash",
        portfolio_value: float = 1000000,
        holdings: Dict[str, float] = None,
        capital_threshold: float = 0.05,
    ) -> StressTestResult:
        return self.stress_engine.run_stress_test(
            portfolio_value=portfolio_value,
            holdings=holdings,
            scenario_name=scenario_name,
            capital_threshold=capital_threshold,
        )

    def run_scenario(
        self,
        scenario_name: str,
        portfolio_sector_weights: Dict[str, float] = None,
    ) -> ScenarioResult:
        return self.scenario_engine.run_scenario(
            scenario_name=scenario_name,
            portfolio_sector_weights=portfolio_sector_weights,
        )

    def evaluate_portfolio_risk(
        self,
        returns: List[float],
        sector_exposures: Dict[str, float],
        factor_exposures: Dict[str, float] = None,
    ) -> PortfolioRisk:
        return self.portfolio_engine.evaluate_portfolio(
            returns=returns,
            sector_exposures=sector_exposures,
            factor_exposures=factor_exposures or {},
        )

    def get_exposure_report(
        self,
        sector_exposure: Dict[str, float],
        country_exposure: Dict[str, float] = None,
        currency_exposure: Dict[str, float] = None,
        asset_exposure: Dict[str, float] = None,
        strategy_exposure: Dict[str, float] = None,
        agent_exposure: Dict[str, float] = None,
    ) -> ExposureReport:
        return self.exposure_engine.generate_report(
            sector_exposure=sector_exposure,
            country_exposure=country_exposure,
            currency_exposure=currency_exposure,
            asset_exposure=asset_exposure,
            strategy_exposure=strategy_exposure,
            agent_exposure=agent_exposure,
        )

    def calculate_position_size(
        self,
        signal_confidence: float = 0.8,
        volatility: float = 0.2,
        liquidity: float = 0.8,
        credit_spread: float = 0.05,
        var_95: float = 0.02,
        trend: float = 0.01,
        index_decline: float = 0.0,
        vix_change: float = 0.0,
        max_portfolio_pct: float = 0.10,
    ) -> PositionSize:
        prediction = self.risk_predictor.predict(
            volatility=volatility,
            liquidity=liquidity,
            credit_spread=credit_spread,
            var_95=var_95,
        )
        regime = self.regime_detector.detect(trend=trend, volatility=volatility)
        bs_event = self.bs_detector.detect(
            index_decline=index_decline, vix_change=vix_change
        )
        return self.position_sizer.size(
            signal_confidence=signal_confidence,
            risk_prediction=prediction,
            market_regime=regime,
            black_swan=bs_event,
            liquidity_score=liquidity,
            max_portfolio_pct=max_portfolio_pct,
        )

    def full_risk_assessment(
        self,
        volatility: float = 0.2,
        liquidity: float = 0.8,
        credit_spread: float = 0.05,
        var_95: float = 0.02,
        trend: float = 0.01,
        volume_ratio: float = 1.0,
        spread: float = 0.0005,
        index_decline: float = 0.0,
        vix_change: float = 0.0,
        volume_surge: float = 1.0,
        bid_ask_spread: float = 0.0005,
        signal_confidence: float = 0.8,
    ) -> AdaptiveControlResult:
        return self.adaptive_controller.evaluate(
            volatility=volatility,
            liquidity=liquidity,
            credit_spread=credit_spread,
            var_95=var_95,
            trend=trend,
            volume_ratio=volume_ratio,
            spread=spread,
            index_decline=index_decline,
            vix_change=vix_change,
            volume_surge=volume_surge,
            bid_ask_spread=bid_ask_spread,
            signal_confidence=signal_confidence,
        )

    def emergency_stop(self) -> AdaptiveControlResult:
        return self.adaptive_controller.emergency_stop()

    def resume_trading(self) -> AdaptiveControlResult:
        return self.adaptive_controller.resume_trading()

    def list_stress_scenarios(self) -> List[str]:
        return self.stress_engine.list_scenarios()

    def list_scenario_engine_scenarios(self) -> List[str]:
        return self.scenario_engine.list_scenarios()
