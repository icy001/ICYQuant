from services.market_intelligence import *


def test_market_observer():
    observer = MarketObserver()
    result = observer.observe("NASDAQ")
    assert result["state"] == "NASDAQ"


def test_market_observer_with_snapshot():
    observer = MarketObserver()
    snapshot = MarketSnapshot(
        symbol="SPX",
        price=4500.0,
        change_pct=0.005,
        volume=2000000,
        avg_volume=1800000,
        volatility=0.012,
        spread_bps=3.0,
        timestamp="10:30",
        trend=MarketTrend.UP,
    )
    result = observer.observe(snapshot)
    assert result["state"]["symbol"] == "SPX"
    assert result["state"]["trend"] == "UP"


def test_market_regime_detector():
    detector = MarketRegimeDetector()
    result = detector.detect("market_data")
    assert result["regime"] == "market_data"


def test_market_regime_bull():
    detector = MarketRegimeDetector()
    indicators = RegimeIndicators(
        trend_strength=0.5,
        volatility=0.015,
        volume_trend="RISING",
        breadth=0.75,
        momentum=0.6,
        vix_level=15.0,
        credit_spread=0.01,
    )
    result = detector.detect(indicators)
    assert result["regime"]["regime"] == "BULL"
    assert result["regime"]["confidence"] > 0.5


def test_macro_intelligence_agent():
    agent = MacroIntelligenceAgent()
    result = agent.analyze("macro_data")
    assert result["macro"] == "macro_data"


def test_macro_bullish_view():
    agent = MacroIntelligenceAgent()
    macro = MacroData(
        interest_rate=3.5,
        inflation_rate=2.5,
        gdp_growth=0.035,
        unemployment_rate=3.8,
        central_bank_stance=CentralBankStance.DOVISH,
        money_supply_growth=0.04,
        yield_curve_spread=0.015,
        credit_spread=0.012,
        dollar_index=100.0,
    )
    result = agent.analyze(macro)
    assert result["macro"]["bias"] in ("BULLISH", "STRONGLY_BULLISH")


def test_economic_cycle_engine():
    engine = EconomicCycleEngine()
    result = engine.analyze("economy")
    assert result["cycle"] == "economy"


def test_economic_cycle_expansion():
    engine = EconomicCycleEngine()
    indicators = CycleIndicators(
        leading_index=0.03,
        coincident_index=0.02,
        lagging_index=0.01,
        capacity_utilization=0.78,
        consumer_confidence=90.0,
        business_sentiment=75.0,
        inventory_to_sales=1.2,
    )
    result = engine.analyze(indicators)
    assert result["cycle"]["phase"] == "EXPANSION"


def test_event_intelligence_engine():
    engine = EventIntelligenceEngine()
    result = engine.analyze("event")
    assert result["event"] == "event"


def test_event_intelligence_with_event():
    engine = EventIntelligenceEngine()
    event = MarketEvent(
        event_id="E001",
        event_type=EventType.FED_MEETING,
        title="FOMC Rate Decision",
        description="Federal Reserve interest rate decision",
        severity=EventSeverity.HIGH,
        expected_date="2026-08-15",
        affected_symbols=["SPX", "TLT", "USD"],
    )
    result = engine.analyze(event)
    assert result["event"]["event_id"] == "E001"
    assert result["event"]["event_type"] == "FED_MEETING"
    assert result["event"]["severity"] == "HIGH"


def test_event_impact_predictor():
    predictor = EventImpactPredictor()
    result = predictor.predict("event")
    assert result["impact"] == "event"


def test_event_impact_fed():
    predictor = EventImpactPredictor()
    report = predictor.predict_fed_impact(-25)
    assert len(report.scenarios) > 0
    assert any(s.asset_class == AssetClass.EQUITY for s in report.scenarios)


def test_news_intelligence_engine():
    engine = NewsIntelligenceEngine()
    result = engine.analyze("news")
    assert result["news"] == "news"


def test_news_intelligence_with_article():
    engine = NewsIntelligenceEngine()
    article = NewsArticle(
        article_id="N001",
        title="Fed signals rate cut amid inflation concerns",
        source="Bloomberg",
        category=NewsCategory.MACRO,
        sentiment=NewsSentiment.POSITIVE,
        relevance_score=0.9,
        impact_score=75.0,
        symbols=["SPX", "TLT"],
    )
    result = engine.analyze(article)
    assert result["news"]["article_id"] == "N001"
    assert result["news"]["category"] == "MACRO"
    assert "rate_cut" in result["news"]["themes"]


def test_sentiment_analysis_engine():
    engine = SentimentAnalysisEngine()
    result = engine.analyze("market")
    assert result["sentiment"] == "market"


def test_sentiment_extreme_fear():
    engine = SentimentAnalysisEngine()
    data = SentimentData(
        source=SentimentSource.OPTIONS,
        fear_greed_score=15,
        confidence=0.8,
        put_call_ratio=1.8,
        vix_level=35.0,
        bullish_pct=0.25,
    )
    result = engine.analyze(data)
    assert result["sentiment"]["overall_index"] == "EXTREME_FEAR"
    assert result["sentiment"]["contrarian_signal"] is True


def test_market_forecast_engine():
    engine = MarketForecastEngine()
    result = engine.forecast("data")
    assert result["forecast"] == "data"


def test_market_forecast_with_input():
    engine = MarketForecastEngine()
    input_data = ForecastInput(
        symbol="SPX",
        current_price=4500.0,
        volatility=0.015,
        trend_strength=0.25,
        sentiment_score=55,
        macro_bias="BULLISH",
        regime="BULL",
    )
    result = engine.forecast(input_data)
    assert result["forecast"]["symbol"] == "SPX"
    assert "base_case" in result["forecast"]
    assert "bull_case" in result["forecast"]
    assert "bear_case" in result["forecast"]


def test_market_memory():
    memory = MarketMemory()
    assert memory.history == []
    memory.save({"event": "Fed meeting", "result": "market up"})
    memory.save({"event": "Earnings season", "result": "volatility spike"})
    assert len(memory.history) == 2
    assert memory.history[0]["event"] == "Fed meeting"
    assert memory.history[1]["result"] == "volatility spike"


def test_market_intelligence_service():
    observer = MarketObserver()
    service = MarketIntelligenceService(observer=observer)
    result = service.analyze("NASDAQ")
    assert result["state"] == "NASDAQ"


def test_full_market_intelligence_workflow():
    """End-to-end autonomous market intelligence workflow."""
    # 1. Market Observer
    observer = MarketObserver()
    snapshot = MarketSnapshot(
        symbol="SPX", price=4500.0, change_pct=0.005,
        volume=2000000, avg_volume=1800000, volatility=0.012,
        spread_bps=3.0, timestamp="10:30", trend=MarketTrend.UP,
    )
    state = observer.observe(snapshot)
    assert state["state"]["symbol"] == "SPX"

    # 2. Regime Detection
    detector = MarketRegimeDetector()
    regime = detector.detect(RegimeIndicators(
        trend_strength=0.5, volatility=0.015, volume_trend="RISING",
        breadth=0.75, momentum=0.6, vix_level=15.0, credit_spread=0.01,
    ))
    assert regime["regime"]["regime"] == "BULL"

    # 3. Macro Intelligence
    macro_agent = MacroIntelligenceAgent()
    macro = macro_agent.analyze(MacroData(
        interest_rate=3.5, inflation_rate=2.5, gdp_growth=0.035,
        unemployment_rate=3.8, central_bank_stance=CentralBankStance.DOVISH,
        money_supply_growth=0.04, yield_curve_spread=0.015,
        credit_spread=0.012, dollar_index=100.0,
    ))
    assert "BULLISH" in macro["macro"]["bias"]

    # 4. Economic Cycle
    cycle_engine = EconomicCycleEngine()
    cycle = cycle_engine.analyze(CycleIndicators(
        leading_index=0.03, coincident_index=0.02, lagging_index=0.01,
        capacity_utilization=0.78, consumer_confidence=90.0,
        business_sentiment=75.0, inventory_to_sales=1.2,
    ))
    assert cycle["cycle"]["phase"] == "EXPANSION"

    # 5. Event Intelligence
    event_engine = EventIntelligenceEngine()
    event = event_engine.analyze(MarketEvent(
        event_id="E001", event_type=EventType.FED_MEETING,
        title="FOMC Decision", description="Rate decision",
        severity=EventSeverity.HIGH, expected_date="2026-08-15",
    ))
    assert event["event"]["severity"] == "HIGH"

    # 6. Event Impact Prediction
    impact_predictor = EventImpactPredictor()
    impact = impact_predictor.predict_fed_impact(-25)
    assert impact.overall_direction == ImpactDirection.POSITIVE

    # 7. News Intelligence
    news_engine = NewsIntelligenceEngine()
    news = news_engine.analyze(NewsArticle(
        article_id="N001", title="Fed signals rate cut",
        source="Bloomberg", category=NewsCategory.MACRO,
        sentiment=NewsSentiment.POSITIVE, relevance_score=0.9, impact_score=75.0,
    ))
    assert "rate_cut" in news["news"]["themes"]

    # 8. Sentiment Analysis
    sentiment_engine = SentimentAnalysisEngine()
    sentiment = sentiment_engine.analyze(SentimentData(
        source=SentimentSource.OPTIONS, fear_greed_score=45,
        confidence=0.8, put_call_ratio=1.0, vix_level=18.0, bullish_pct=0.5,
    ))
    assert sentiment["sentiment"]["overall_index"] == "NEUTRAL"

    # 9. Market Forecast
    forecast_engine = MarketForecastEngine()
    forecast = forecast_engine.forecast(ForecastInput(
        symbol="SPX", current_price=4500.0, volatility=0.015,
        trend_strength=0.25, sentiment_score=55, macro_bias="BULLISH",
        regime="BULL",
    ))
    assert forecast["forecast"]["symbol"] == "SPX"

    # 10. Market Memory
    memory = MarketMemory()
    memory.save(MarketMemoryEntry(
        event_type="REGIME_CHANGE", symbol="SPX",
        description="Market entered bull regime",
        regime="BULL", sentiment="GREED",
        forecast_result="UP", actual_result="UP",
        lesson="Bull regime correctly identified",
    ))
    assert len(memory.history) == 1

    # 11. Market Intelligence Service
    service = MarketIntelligenceService(observer=observer)
    result = service.analyze(observer)
    assert result is not None
