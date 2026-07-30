from dataclasses import dataclass, field
from typing import Dict, Optional

from .market_regime import MarketRegime
from .black_swan import BlackSwanEvent
from .risk_predictor import RiskPrediction


@dataclass
class RiskLimitConfig:
    max_drawdown_pct: float
    max_position_pct: float
    max_leverage: float
    max_daily_loss_pct: float
    max_sector_exposure_pct: float


@dataclass
class AdaptiveLimitResult:
    base_config: RiskLimitConfig
    adjusted_config: RiskLimitConfig
    adjustment_reasons: list
    tightened: bool


class AdaptiveLimitManager:
    def __init__(self, base_config: RiskLimitConfig = None):
        self.base_config = base_config or RiskLimitConfig(
            max_drawdown_pct=0.10,
            max_position_pct=0.10,
            max_leverage=3.0,
            max_daily_loss_pct=0.03,
            max_sector_exposure_pct=0.40,
        )
        self.current_config = self.base_config

    def apply_market_regime(
        self, regime: MarketRegime
    ) -> AdaptiveLimitResult:
        adjusted = RiskLimitConfig(
            max_drawdown_pct=self.base_config.max_drawdown_pct,
            max_position_pct=regime.max_position_pct,
            max_leverage=regime.max_leverage,
            max_daily_loss_pct=self.base_config.max_daily_loss_pct,
            max_sector_exposure_pct=self.base_config.max_sector_exposure_pct,
        )

        reasons = [f"Market Regime: {regime.regime_type}"]

        if regime.regime_type in ("RISK_OFF", "BEAR", "LOW_LIQUIDITY"):
            adjusted.max_drawdown_pct = self.base_config.max_drawdown_pct * 0.5
            adjusted.max_daily_loss_pct = self.base_config.max_daily_loss_pct * 0.5
            adjusted.max_sector_exposure_pct = self.base_config.max_sector_exposure_pct * 0.7
            reasons.append("Limits tightened due to adverse market conditions")
        elif regime.regime_type == "HIGH_VOLATILITY":
            adjusted.max_drawdown_pct = self.base_config.max_drawdown_pct * 0.7
            adjusted.max_daily_loss_pct = self.base_config.max_daily_loss_pct * 0.7
            reasons.append("Limits tightened due to high volatility")

        self.current_config = adjusted
        return AdaptiveLimitResult(
            base_config=self.base_config,
            adjusted_config=adjusted,
            adjustment_reasons=reasons,
            tightened=adjusted.max_drawdown_pct < self.base_config.max_drawdown_pct,
        )

    def apply_black_swan(
        self, event: BlackSwanEvent
    ) -> AdaptiveLimitResult:
        adjusted = RiskLimitConfig(
            max_drawdown_pct=self.base_config.max_drawdown_pct,
            max_position_pct=self.base_config.max_position_pct,
            max_leverage=self.base_config.max_leverage,
            max_daily_loss_pct=self.base_config.max_daily_loss_pct,
            max_sector_exposure_pct=self.base_config.max_sector_exposure_pct,
        )

        reasons = [f"Black Swan Level: {event.level}"]

        if event.level == "EXTREME":
            adjusted.max_position_pct = 0.0
            adjusted.max_leverage = 1.0
            adjusted.max_drawdown_pct = 0.02
            adjusted.max_daily_loss_pct = 0.01
            reasons.append("All new positions halted - Extreme risk")
        elif event.level == "CRITICAL":
            adjusted.max_position_pct = self.base_config.max_position_pct * 0.2
            adjusted.max_leverage = self.base_config.max_leverage * 0.5
            adjusted.max_drawdown_pct = self.base_config.max_drawdown_pct * 0.3
            adjusted.max_daily_loss_pct = self.base_config.max_daily_loss_pct * 0.3
            reasons.append("Severe position reduction - Critical risk")
        elif event.level == "WARNING":
            adjusted.max_position_pct = self.base_config.max_position_pct * 0.5
            adjusted.max_leverage = self.base_config.max_leverage * 0.7
            adjusted.max_drawdown_pct = self.base_config.max_drawdown_pct * 0.6
            reasons.append("Moderate tightening - Warning level")

        self.current_config = adjusted
        return AdaptiveLimitResult(
            base_config=self.base_config,
            adjusted_config=adjusted,
            adjustment_reasons=reasons,
            tightened=adjusted.max_drawdown_pct < self.base_config.max_drawdown_pct,
        )

    def apply_risk_prediction(
        self, prediction: RiskPrediction
    ) -> AdaptiveLimitResult:
        adjusted = RiskLimitConfig(
            max_drawdown_pct=self.base_config.max_drawdown_pct,
            max_position_pct=self.base_config.max_position_pct,
            max_leverage=self.base_config.max_leverage,
            max_daily_loss_pct=self.base_config.max_daily_loss_pct,
            max_sector_exposure_pct=self.base_config.max_sector_exposure_pct,
        )

        reasons = [f"Risk Score: {prediction.risk_score} ({prediction.risk_level})"]

        if prediction.risk_level == "LOW":
            self.current_config = adjusted
            return AdaptiveLimitResult(
                base_config=self.base_config,
                adjusted_config=adjusted,
                adjustment_reasons=reasons,
                tightened=False,
            )

        if prediction.risk_level == "HIGH":
            factor = max(0.3, 1.0 - (prediction.risk_score / 150))
            adjusted.max_position_pct = self.base_config.max_position_pct * factor
            adjusted.max_leverage = self.base_config.max_leverage * factor
            adjusted.max_drawdown_pct = self.base_config.max_drawdown_pct * factor
            adjusted.max_daily_loss_pct = self.base_config.max_daily_loss_pct * factor
            reasons.append(f"Limits adjusted by factor {factor:.2f}")
        elif prediction.risk_level == "MEDIUM":
            adjusted.max_position_pct = self.base_config.max_position_pct * 0.8
            adjusted.max_drawdown_pct = self.base_config.max_drawdown_pct * 0.8
            reasons.append("Moderate tightening for medium risk")

        self.current_config = adjusted
        return AdaptiveLimitResult(
            base_config=self.base_config,
            adjusted_config=adjusted,
            adjustment_reasons=reasons,
            tightened=adjusted.max_drawdown_pct < self.base_config.max_drawdown_pct,
        )

    def get_current_config(self) -> RiskLimitConfig:
        return self.current_config
