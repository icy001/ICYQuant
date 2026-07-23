"""
Trading decision engine.
"""

from .trading_decision import TradingDecision


class TradingDecisionEngine:

    def decide(
        self,
        symbol,
        analysis,
    ):

        return TradingDecision(
            symbol=symbol,
            action="HOLD",
            confidence=0.5,
            reasoning=analysis,
        )