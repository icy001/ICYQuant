"""
Market intelligence service.
"""


class MarketIntelligenceService:

    def __init__(
        self,
        market_agent,
        sentiment_engine,
        regime_detector,
    ):

        self.market_agent = market_agent

        self.sentiment_engine = sentiment_engine

        self.regime_detector = regime_detector

    def analyze(
        self,
        context,
    ):

        intelligence = self.market_agent.analyze(
            context
        )

        sentiment = self.sentiment_engine.analyze(
            intelligence
        )

        regime = self.regime_detector.detect(
            intelligence
        )

        return {
            "intelligence": intelligence,
            "sentiment": sentiment,
            "regime": regime,
        }