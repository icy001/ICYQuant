from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ImpactDirection(str, Enum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    NEUTRAL = "NEUTRAL"
    UNCERTAIN = "UNCERTAIN"


class AssetClass(str, Enum):
    EQUITY = "EQUITY"
    BOND = "BOND"
    COMMODITY = "COMMODITY"
    CURRENCY = "CURRENCY"
    CRYPTO = "CRYPTO"


@dataclass
class ImpactScenario:
    asset_class: AssetClass
    symbol: str
    direction: ImpactDirection
    magnitude_bps: float
    probability: float
    reasoning: str = ""


@dataclass
class EventImpactReport:
    event_id: str
    event_title: str
    scenarios: List[ImpactScenario] = field(default_factory=list)
    overall_direction: ImpactDirection = ImpactDirection.UNCERTAIN
    confidence: float = 0.5
    time_horizon: str = "1W"


class EventImpactPredictor:
    """Event Impact Prediction Engine - predicts market impact of events across assets."""

    def __init__(self):
        self.prediction_history: List[EventImpactReport] = []

    def predict(self, event):
        """Predict the market impact of an event.

        Args:
            event: Event data - can be EventImpactReport dataclass or dict/symbol.

        Returns:
            Dict containing impact prediction result.
        """
        if isinstance(event, EventImpactReport):
            return self._predict_impact(event)
        return {"impact": event}

    def _predict_impact(self, event: EventImpactReport) -> dict:
        return {
            "impact": {
                "event_id": event.event_id,
                "event_title": event.event_title,
                "overall_direction": event.overall_direction.value,
                "confidence": round(event.confidence, 2),
                "time_horizon": event.time_horizon,
                "scenarios": [
                    {
                        "asset_class": s.asset_class.value,
                        "symbol": s.symbol,
                        "direction": s.direction.value,
                        "magnitude_bps": s.magnitude_bps,
                        "probability": round(s.probability, 2),
                        "reasoning": s.reasoning,
                    }
                    for s in event.scenarios
                ],
            }
        }

    def predict_fed_impact(self, rate_change_bps: int) -> EventImpactReport:
        """Generate impact prediction for Fed rate decision."""
        scenarios = []
        direction = ImpactDirection.POSITIVE if rate_change_bps < 0 else ImpactDirection.NEGATIVE

        if rate_change_bps < 0:
            scenarios.extend([
                ImpactScenario(AssetClass.EQUITY, "SPX", ImpactDirection.POSITIVE, 50.0, 0.7, "Rate cut supports equity valuations"),
                ImpactScenario(AssetClass.BOND, "TLT", ImpactDirection.POSITIVE, 30.0, 0.8, "Bond prices rise as yields fall"),
                ImpactScenario(AssetClass.CURRENCY, "USD", ImpactDirection.NEGATIVE, -40.0, 0.6, "USD weakens on lower rates"),
                ImpactScenario(AssetClass.COMMODITY, "GLD", ImpactDirection.POSITIVE, 20.0, 0.6, "Gold benefits from weaker USD"),
            ])
        elif rate_change_bps > 0:
            scenarios.extend([
                ImpactScenario(AssetClass.EQUITY, "SPX", ImpactDirection.NEGATIVE, -30.0, 0.6, "Rate hike pressures valuations"),
                ImpactScenario(AssetClass.BOND, "TLT", ImpactDirection.NEGATIVE, -25.0, 0.8, "Bond prices fall as yields rise"),
                ImpactScenario(AssetClass.CURRENCY, "USD", ImpactDirection.POSITIVE, 30.0, 0.7, "USD strengthens on higher rates"),
            ])
        else:
            scenarios.append(
                ImpactScenario(AssetClass.EQUITY, "SPX", ImpactDirection.NEUTRAL, 0.0, 0.5, "No change - market neutral")
            )

        return EventImpactReport(
            event_id=f"FED_{abs(rate_change_bps)}",
            event_title=f"Fed Rate Change: {rate_change_bps:+d}bps",
            scenarios=scenarios,
            overall_direction=direction,
            confidence=0.7,
        )
