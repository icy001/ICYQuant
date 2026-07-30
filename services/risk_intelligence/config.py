"""Risk Intelligence configuration module.

Defines all configuration dataclasses and enums for the global
risk intelligence and adaptive risk engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ============================================================================
# Enums
# ============================================================================


class RiskLevel(str, Enum):
    """Risk severity levels."""

    LOW = "low"          # 0-30
    MEDIUM = "medium"    # 31-70
    HIGH = "high"        # 71-100
    CRITICAL = "critical"  # Emergency stop triggered


class MarketRegime(str, Enum):
    """Market regime classification."""

    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOLATILITY = "high_volatility"
    LOW_LIQUIDITY = "low_liquidity"
    RISK_OFF = "risk_off"
    CRISIS = "crisis"
    UNKNOWN = "unknown"


class EmergencyLevel(str, Enum):
    """Emergency control levels."""

    LEVEL_1 = "level_1"  # Alert only
    LEVEL_2 = "level_2"  # Restrict positions
    LEVEL_3 = "level_3"  # Stop trading, cancel orders


class StressScenarioType(str, Enum):
    """Types of stress testing scenarios."""

    HISTORICAL = "historical"    # Replay historical events
    HYPOTHETICAL = "hypothetical"  # Custom scenarios
    REGULATORY = "regulatory"    # Basel/CCAR style
    REVERSE = "reverse"          # Reverse stress test


class PositionSizingMethod(str, Enum):
    """Position sizing methodologies."""

    KELLY = "kelly"
    RISK_PARITY = "risk_parity"
    EQUAL_WEIGHT = "equal_weight"
    VOL_TARGETING = "vol_targeting"
    MAX_DRAWDOWN = "max_drawdown"
    ADAPTIVE = "adaptive"


class LimitType(str, Enum):
    """Types of risk limits."""

    POSITION_SIZE = "position_size"
    LEVERAGE = "leverage"
    GROSS_EXPOSURE = "gross_exposure"
    NET_EXPOSURE = "net_exposure"
    SECTOR_CONCENTRATION = "sector_concentration"
    SINGLE_STOCK = "single_stock"
    COUNTRY = "country"
    CURRENCY = "currency"
    DRAWDOWN = "drawdown"
    VAR = "var"
    STRATEGY = "strategy"


class ExposureDimension(str, Enum):
    """Dimensions for exposure analysis."""

    SECTOR = "sector"
    COUNTRY = "country"
    CURRENCY = "currency"
    ASSET_CLASS = "asset_class"
    SINGLE_STOCK = "single_stock"
    STRATEGY = "strategy"
    AGENT = "agent"
    FACTOR = "factor"
    MARKET_CAP = "market_cap"


class BlackSwanIndicator(str, Enum):
    """Black swan detection indicators."""

    INDEX_CRASH = "index_crash"
    VOLUME_SURGE = "volume_surge"
    VOLATILITY_SPIKE = "volatility_spike"
    LIQUIDITY_DROPOUT = "liquidity_dropout"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    SPREAD_EXPLOSION = "spread_explosion"


# ============================================================================
# Configuration Dataclasses
# ============================================================================


@dataclass
class RiskPredictorConfig:
    """AI risk predictor configuration."""

    lookback_window: int = 60
    prediction_horizon: int = 5
    confidence_threshold: float = 0.7
    feature_count: int = 20
    update_frequency_seconds: int = 60
    low_risk_threshold: int = 30
    medium_risk_threshold: int = 70
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class MarketRegimeConfig:
    """Market regime detection configuration."""

    detection_window: int = 60
    regime_change_threshold: float = 0.6
    volatility_lookback: int = 20
    trend_lookback: int = 50
    min_regime_duration_days: int = 5
    metadata: Dict[str, str] = field(default_factory=dict)

    # Regime-specific parameters
    bull_max_position_pct: float = 10.0
    bear_max_position_pct: float = 5.0
    crisis_max_position_pct: float = 2.0
    risk_off_max_position_pct: float = 3.0
    default_max_position_pct: float = 7.0


@dataclass
class PositionSizerConfig:
    """Dynamic position sizing configuration."""

    method: PositionSizingMethod = PositionSizingMethod.ADAPTIVE
    kelly_fraction: float = 0.25  # Fractional Kelly
    max_position_pct: float = 10.0
    min_position_pct: float = 0.5
    risk_per_trade_pct: float = 1.0
    volatility_target: float = 15.0  # Annualized vol target
    max_leverage: float = 3.0
    min_signal_confidence: float = 0.5
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class StressTestConfig:
    """Stress testing configuration."""

    default_num_simulations: int = 10000
    confidence_level: float = 0.99
    max_scenarios_per_run: int = 100
    enable_historical: bool = True
    enable_hypothetical: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ScenarioEngineConfig:
    """Scenario engine configuration."""

    max_scenarios: int = 50
    enable_custom_scenarios: bool = True
    scenario_retention_days: int = 365
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class BlackSwanConfig:
    """Black swan detection configuration."""

    crash_threshold_pct: float = -5.0
    volume_surge_multiplier: float = 5.0
    volatility_spike_multiplier: float = 3.0
    liquidity_dropout_threshold_pct: float = 0.1
    auto_protection: bool = True
    protection_actions: List[str] = field(default_factory=lambda: [
        "stop_opening",
        "reduce_leverage",
        "freeze_high_risk",
        "activate_safe_haven",
    ])
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class PortfolioRiskConfig:
    """Portfolio risk engine configuration."""

    var_confidence: float = 0.99
    cvar_confidence: float = 0.975
    var_lookback: int = 252
    covariance_half_life: int = 60
    max_sector_exposure_pct: float = 40.0
    max_single_stock_pct: float = 15.0
    max_country_exposure_pct: float = 50.0
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class LimitManagerConfig:
    """Risk limit manager configuration."""

    enable_adaptive_limits: bool = True
    tightening_factor: float = 0.5  # Reduce limits by 50% in high risk
    loosening_factor: float = 1.0  # Return to normal in low risk
    max_drawdown_limit_pct: float = 15.0
    daily_loss_limit_pct: float = 5.0
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExposureEngineConfig:
    """Exposure engine configuration."""

    max_gross_exposure: float = 200.0
    max_net_exposure: float = 100.0
    max_sector_exposure_pct: float = 40.0
    max_agent_risk_budget_pct: float = 35.0
    max_strategy_risk_budget_pct: float = 25.0
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class AdaptiveControllerConfig:
    """Adaptive risk controller configuration."""

    level_1_threshold: int = 50
    level_2_threshold: int = 70
    level_3_threshold: int = 90
    auto_recovery_enabled: bool = True
    auto_recovery_cooldown_minutes: int = 30
    require_manual_recovery_level_3: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class RiskServiceConfig:
    """Master configuration for the risk intelligence service."""

    predictor: RiskPredictorConfig = field(default_factory=RiskPredictorConfig)
    regime: MarketRegimeConfig = field(default_factory=MarketRegimeConfig)
    position_sizer: PositionSizerConfig = field(default_factory=PositionSizerConfig)
    stress_test: StressTestConfig = field(default_factory=StressTestConfig)
    scenario: ScenarioEngineConfig = field(default_factory=ScenarioEngineConfig)
    black_swan: BlackSwanConfig = field(default_factory=BlackSwanConfig)
    portfolio_risk: PortfolioRiskConfig = field(default_factory=PortfolioRiskConfig)
    limit_manager: LimitManagerConfig = field(default_factory=LimitManagerConfig)
    exposure: ExposureEngineConfig = field(default_factory=ExposureEngineConfig)
    adaptive: AdaptiveControllerConfig = field(default_factory=AdaptiveControllerConfig)
    metadata: Dict[str, str] = field(default_factory=dict)
