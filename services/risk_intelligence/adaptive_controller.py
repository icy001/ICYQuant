from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .risk_predictor import RiskPredictor, RiskPrediction
from .market_regime import MarketRegimeDetector, MarketRegime
from .black_swan import BlackSwanDetector, BlackSwanEvent
from .limit_manager import AdaptiveLimitManager, AdaptiveLimitResult
from .position_sizer import DynamicPositionSizer, PositionSize


class EmergencyLevel(Enum):
    NORMAL = "NORMAL"
    ALERT = "ALERT"
    RESTRICT = "RESTRICT"
    HALT = "HALT"


@dataclass
class EmergencyAction:
    level: str
    cancel_orders: bool
    disable_new_orders: bool
    freeze_agents: bool
    notify_admin: bool


@dataclass
class AdaptiveControlResult:
    emergency_level: str
    risk_prediction: Optional[RiskPrediction]
    market_regime: Optional[MarketRegime]
    black_swan_event: Optional[BlackSwanEvent]
    adjusted_limits: Optional[AdaptiveLimitResult]
    position_size: Optional[PositionSize]
    actions: EmergencyAction
    can_trade: bool


class AdaptiveController:
    def __init__(self):
        self.risk_predictor = RiskPredictor()
        self.regime_detector = MarketRegimeDetector()
        self.black_swan_detector = BlackSwanDetector()
        self.limit_manager = AdaptiveLimitManager()
        self.position_sizer = DynamicPositionSizer()

    def evaluate(
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
        prediction = self.risk_predictor.predict(
            volatility=volatility,
            liquidity=liquidity,
            credit_spread=credit_spread,
            var_95=var_95,
        )

        regime = self.regime_detector.detect(
            trend=trend,
            volatility=volatility,
            volume_ratio=volume_ratio,
            spread=spread,
        )

        bs_event = self.black_swan_detector.detect(
            index_decline=index_decline,
            vix_change=vix_change,
            volume_surge=volume_surge,
            bid_ask_spread=bid_ask_spread,
        )

        if bs_event.detected:
            adjusted_limits = self.limit_manager.apply_black_swan(bs_event)
        elif prediction.risk_level == "HIGH":
            adjusted_limits = self.limit_manager.apply_risk_prediction(prediction)
        else:
            adjusted_limits = self.limit_manager.apply_market_regime(regime)

        current_config = self.limit_manager.get_current_config()

        position_size = self.position_sizer.size(
            signal_confidence=signal_confidence,
            risk_prediction=prediction,
            market_regime=regime,
            black_swan=bs_event,
            liquidity_score=liquidity,
            max_portfolio_pct=current_config.max_position_pct,
        )

        emergency_level = EmergencyLevel.NORMAL.value
        actions = EmergencyAction(
            level=EmergencyLevel.NORMAL.value,
            cancel_orders=False,
            disable_new_orders=False,
            freeze_agents=False,
            notify_admin=False,
        )

        if bs_event.level == "EXTREME":
            emergency_level = EmergencyLevel.HALT.value
            actions = EmergencyAction(
                level=EmergencyLevel.HALT.value,
                cancel_orders=True,
                disable_new_orders=True,
                freeze_agents=True,
                notify_admin=True,
            )
        elif bs_event.level == "CRITICAL" or prediction.risk_level == "HIGH":
            emergency_level = EmergencyLevel.RESTRICT.value
            actions = EmergencyAction(
                level=EmergencyLevel.RESTRICT.value,
                cancel_orders=False,
                disable_new_orders=True,
                freeze_agents=False,
                notify_admin=True,
            )
        elif bs_event.level == "WARNING" or regime.regime_type in ("RISK_OFF", "BEAR"):
            emergency_level = EmergencyLevel.ALERT.value
            actions = EmergencyAction(
                level=EmergencyLevel.ALERT.value,
                cancel_orders=False,
                disable_new_orders=False,
                freeze_agents=False,
                notify_admin=True,
            )

        can_trade = (
            emergency_level != EmergencyLevel.HALT.value
            and position_size.adjusted_pct > 0
        )

        return AdaptiveControlResult(
            emergency_level=emergency_level,
            risk_prediction=prediction,
            market_regime=regime,
            black_swan_event=bs_event,
            adjusted_limits=adjusted_limits,
            position_size=position_size,
            actions=actions,
            can_trade=can_trade,
        )

    def emergency_stop(self) -> AdaptiveControlResult:
        self.limit_manager.current_config.max_position_pct = 0.0
        self.limit_manager.current_config.max_leverage = 1.0

        return AdaptiveControlResult(
            emergency_level=EmergencyLevel.HALT.value,
            risk_prediction=None,
            market_regime=None,
            black_swan_event=None,
            adjusted_limits=None,
            position_size=None,
            actions=EmergencyAction(
                level=EmergencyLevel.HALT.value,
                cancel_orders=True,
                disable_new_orders=True,
                freeze_agents=True,
                notify_admin=True,
            ),
            can_trade=False,
        )

    def resume_trading(self) -> AdaptiveControlResult:
        self.limit_manager.current_config = self.limit_manager.base_config

        return AdaptiveControlResult(
            emergency_level=EmergencyLevel.NORMAL.value,
            risk_prediction=None,
            market_regime=None,
            black_swan_event=None,
            adjusted_limits=None,
            position_size=None,
            actions=EmergencyAction(
                level=EmergencyLevel.NORMAL.value,
                cancel_orders=False,
                disable_new_orders=False,
                freeze_agents=False,
                notify_admin=False,
            ),
            can_trade=True,
        )
