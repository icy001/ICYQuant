"""AI Risk Intelligence Engine – dynamic risk management layer.

Provides:
- Dynamic Risk Assessment
- AI Risk Prediction
- Stress Testing
- Scenario Simulation
- Risk Explanation
- Systemic Risk Detection
- Crisis Early Warning
- Volatility Regime Prediction
- Portfolio Defense Automation
- Risk Intelligence Service
"""

from .risk import RiskProfile, classify_risk_level, compute_risk_score
from .assessment import RiskAssessmentEngine
from .prediction import RiskPredictionEngine, RiskPrediction
from .stress_test import StressTestEngine, StressTestResult
from .scenario import ScenarioSimulator, Scenario, DEFAULT_SCENARIOS
from .explanation import RiskExplanationEngine, RiskExplanation
from .systemic_risk import (
    SystemicRiskDetector,
    SystemicRiskResult,
    SystemicRiskLevel,
    ContagionChannel,
    ContagionSignal,
)
from .crisis_warning import (
    CrisisEarlyWarningSystem,
    CrisisWarningResult,
    CrisisWarning,
    CrisisPhase,
    WarningSeverity,
    WarningType,
)
from .volatility_regime import (
    VolatilityRegimePredictor,
    RegimePrediction,
    VolatilityForecast,
    VolatilityRegime,
    RegimeTransition,
    TermStructureState,
)
from .defense import (
    PortfolioDefenseAutomation,
    DefensePlan,
    DefenseAction,
    DefenseLevel,
    DefenseActionType,
    HedgeInstrument,
)
from .service import RiskIntelligenceService

__all__ = [
    "RiskProfile",
    "classify_risk_level",
    "compute_risk_score",
    "RiskAssessmentEngine",
    "RiskPredictionEngine",
    "RiskPrediction",
    "StressTestEngine",
    "StressTestResult",
    "ScenarioSimulator",
    "Scenario",
    "DEFAULT_SCENARIOS",
    "RiskExplanationEngine",
    "RiskExplanation",
    # Systemic Risk
    "SystemicRiskDetector",
    "SystemicRiskResult",
    "SystemicRiskLevel",
    "ContagionChannel",
    "ContagionSignal",
    # Crisis Warning
    "CrisisEarlyWarningSystem",
    "CrisisWarningResult",
    "CrisisWarning",
    "CrisisPhase",
    "WarningSeverity",
    "WarningType",
    # Volatility Regime
    "VolatilityRegimePredictor",
    "RegimePrediction",
    "VolatilityForecast",
    "VolatilityRegime",
    "RegimeTransition",
    "TermStructureState",
    # Portfolio Defense
    "PortfolioDefenseAutomation",
    "DefensePlan",
    "DefenseAction",
    "DefenseLevel",
    "DefenseActionType",
    "HedgeInstrument",
    # Service
    "RiskIntelligenceService",
]
