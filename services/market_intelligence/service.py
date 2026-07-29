from typing import Any, Dict

from .observer import MarketObserver
from .regime import MarketRegimeDetector
from .macro import MacroIntelligenceAgent
from .cycle import EconomicCycleEngine
from .event import EventIntelligenceEngine
from .impact import EventImpactPredictor
from .news import NewsIntelligenceEngine
from .sentiment import SentimentAnalysisEngine
from .forecast import MarketForecastEngine
from .memory import MarketMemory


class MarketIntelligenceService:
    """Market Intelligence Service - orchestrates the full autonomous market intelligence loop."""

    def __init__(self, observer):
        self.observer = observer
        self.regime_detector = MarketRegimeDetector()
        self.macro_agent = MacroIntelligenceAgent()
        self.cycle_engine = EconomicCycleEngine()
        self.event_engine = EventIntelligenceEngine()
        self.impact_predictor = EventImpactPredictor()
        self.news_engine = NewsIntelligenceEngine()
        self.sentiment_engine = SentimentAnalysisEngine()
        self.forecast_engine = MarketForecastEngine()
        self.memory = MarketMemory()

    def analyze(self, market):
        """Analyze market conditions through the observer.

        Args:
            market: Market data to analyze.

        Returns:
            Dict containing market state from the observer.
        """
        return self.observer.observe(market)

    def run_full_loop(self, market_data, macro_data=None, event_data=None, news_data=None, sentiment_data=None) -> Dict[str, Any]:
        """Run the complete autonomous market intelligence loop.

        Steps:
        1. Market Observation
        2. Regime Detection
        3. Macro Analysis
        4. Economic Cycle Analysis
        5. Event Intelligence
        6. Event Impact Prediction
        7. News Analysis
        8. Sentiment Analysis
        9. Market Forecast
        10. Memory Recording
        """
        # Step 1: Observe market
        observation = self.observer.observe(market_data)

        # Step 2: Detect regime
        regime = self.regime_detector.detect(market_data)

        # Step 3: Macro analysis
        macro = self.macro_agent.analyze(macro_data) if macro_data else {"macro": "no data"}

        # Step 4: Economic cycle
        cycle = self.cycle_engine.analyze(market_data)

        # Step 5: Event intelligence
        event = self.event_engine.analyze(event_data) if event_data else {"event": "no events"}

        # Step 6: Event impact prediction
        impact = self.impact_predictor.predict(event_data) if event_data else {"impact": "no events"}

        # Step 7: News analysis
        news = self.news_engine.analyze(news_data) if news_data else {"news": "no news"}

        # Step 8: Sentiment analysis
        sentiment = self.sentiment_engine.analyze(sentiment_data) if sentiment_data else {"sentiment": "no data"}

        # Step 9: Market forecast
        forecast = self.forecast_engine.forecast(market_data)

        # Step 10: Save to memory
        self.memory.save(market_data)

        return {
            "observation": observation,
            "regime": regime,
            "macro": macro,
            "cycle": cycle,
            "event": event,
            "impact": impact,
            "news": news,
            "sentiment": sentiment,
            "forecast": forecast,
            "status": "COMPLETED",
        }
