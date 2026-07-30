from dataclasses import dataclass
from enum import Enum


class BlackSwanLevel(Enum):
    NONE = "NONE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EXTREME = "EXTREME"


@dataclass
class BlackSwanEvent:
    level: str
    detected: bool
    index_decline_pct: float
    volatility_spike: float
    liquidity_drought: bool
    abnormal_volume: bool


class BlackSwanDetector:
    def detect(
        self,
        index_decline: float = 0.0,
        vix_change: float = 0.0,
        volume_surge: float = 1.0,
        bid_ask_spread: float = 0.0005,
    ) -> BlackSwanEvent:
        level = BlackSwanLevel.NONE.value
        detected = False

        if index_decline <= -0.05 or vix_change > 0.5 or volume_surge > 3.0 or bid_ask_spread > 0.005:
            level = BlackSwanLevel.WARNING.value
            detected = True

        if index_decline <= -0.10 or vix_change > 1.0 or volume_surge > 5.0 or bid_ask_spread > 0.01:
            level = BlackSwanLevel.CRITICAL.value
            detected = True

        if index_decline <= -0.15 or vix_change > 1.5 or volume_surge > 8.0 or bid_ask_spread > 0.02:
            level = BlackSwanLevel.EXTREME.value
            detected = True

        return BlackSwanEvent(
            level=level,
            detected=detected,
            index_decline_pct=index_decline,
            volatility_spike=vix_change,
            liquidity_drought=bid_ask_spread > 0.005,
            abnormal_volume=volume_surge > 3.0,
        )
