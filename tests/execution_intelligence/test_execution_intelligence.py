from services.execution_intelligence import *


def test_execution_trader():
    trader = AIExecutionTrader()
    result = trader.decide("NVDA order")
    assert result["execution_plan"] == "NVDA order"


def test_ai_execution_trader_agent():
    trader = AIExecutionTrader()
    result = trader.decide({"symbol": "AAPL", "side": "BUY", "quantity": 5000})
    assert result["execution_plan"]["symbol"] == "AAPL"
    assert result["execution_plan"]["side"] == "BUY"
    assert result["execution_plan"]["quantity"] == 5000


def test_execution_planner():
    planner = ExecutionPlanner()
    result = planner.plan({"symbol": "TSLA", "quantity": 2000})
    assert result["plan"]["symbol"] == "TSLA"
    assert result["plan"]["quantity"] == 2000


def test_smart_order_router():
    router = SmartOrderRouter()
    result = router.route({"symbol": "GOOGL", "side": "BUY", "quantity": 1000})
    assert result["route"]["symbol"] == "GOOGL"
    assert result["route"]["quantity"] == 1000


def test_market_impact_predictor():
    predictor = MarketImpactPredictor()
    result = predictor.predict({"symbol": "META", "quantity": 5000})
    assert result["impact"]["symbol"] == "META"
    assert result["impact"]["quantity"] == 5000


def test_execution_algorithm_engine():
    engine = ExecutionAlgorithmEngine()
    result = engine.execute("VWAP")
    assert result["algorithm"] == "VWAP"


def test_slippage_control_engine():
    engine = SlippageControlEngine()
    result = engine.measure({"trade_id": "T001", "expected_price": 150.0, "executed_price": 150.25})
    assert result["slippage"]["trade_id"] == "T001"


def test_liquidity_detection_engine():
    engine = LiquidityDetectionEngine()
    result = engine.detect({"symbol": "NVDA", "spread_bps": 3.0})
    assert result["liquidity"]["symbol"] == "NVDA"
    assert result["liquidity"]["spread_bps"] == 3.0


def test_adaptive_execution_engine():
    engine = AdaptiveExecutionEngine()
    result = engine.adjust({"market": "volatile", "slippage": 20})
    assert result["adjustment"]["market"] == "volatile"
    assert result["adjustment"]["slippage"] == 20


def test_execution_quality_analyzer():
    analyzer = ExecutionQualityAnalyzer()
    result = analyzer.analyze({"order_id": "O001", "implementation_shortfall_bps": 3.0})
    assert result["quality"]["order_id"] == "O001"


def test_execution_memory():
    memory = ExecutionMemory()
    assert memory.history == []
    memory.save({"order": "NVDA", "result": "filled"})
    memory.save({"order": "AAPL", "result": "partial"})
    assert len(memory.history) == 2
    assert memory.history[0]["order"] == "NVDA"
    assert memory.history[1]["result"] == "partial"


def test_execution_intelligence_service():
    trader = AIExecutionTrader()
    service = ExecutionIntelligenceService(trader=trader)
    result = service.execute("NVDA order")
    assert result["execution_plan"] == "NVDA order"


def test_full_execution_workflow():
    """End-to-end autonomous execution workflow."""
    # 1. AI Execution Trader decides
    trader = AIExecutionTrader()
    decision = trader.decide({"symbol": "NVDA", "side": "BUY", "quantity": 10000})
    assert decision["execution_plan"]["symbol"] == "NVDA"
    assert decision["execution_plan"]["quantity"] == 10000

    # 2. Execution Planning
    planner = ExecutionPlanner()
    plan = planner.plan({"symbol": "NVDA", "quantity": 10000, "side": "BUY"})
    assert plan["plan"]["symbol"] == "NVDA"

    # 3. Market Impact Prediction
    impact = MarketImpactPredictor()
    impact_result = impact.predict({"symbol": "NVDA", "quantity": 10000})
    assert impact_result["impact"]["symbol"] == "NVDA"

    # 4. Smart Order Routing
    router = SmartOrderRouter()
    route = router.route({"symbol": "NVDA", "side": "BUY", "quantity": 10000})
    assert route["route"]["symbol"] == "NVDA"

    # 5. Execution Algorithm
    algo = ExecutionAlgorithmEngine()
    algo_result = algo.execute("VWAP")
    assert algo_result["algorithm"] == "VWAP"

    # 6. Slippage Control
    slippage = SlippageControlEngine()
    slip_result = slippage.measure({
        "trade_id": "NVDA-001",
        "expected_price": 450.0,
        "executed_price": 450.50,
    })
    assert slip_result["slippage"]["trade_id"] == "NVDA-001"

    # 7. Liquidity Detection
    liquidity = LiquidityDetectionEngine()
    liq_result = liquidity.detect({"symbol": "NVDA", "spread_bps": 2.5})
    assert liq_result["liquidity"]["symbol"] == "NVDA"

    # 8. Adaptive Execution
    adaptive = AdaptiveExecutionEngine()
    adj_result = adaptive.adjust({"market": "stable", "slippage": 5})
    assert adj_result["adjustment"]["market"] == "stable"

    # 9. Quality Analysis
    quality = ExecutionQualityAnalyzer()
    qual_result = quality.analyze({
        "order_id": "NVDA-001",
        "implementation_shortfall_bps": 1.5,
    })
    assert qual_result["quality"]["order_id"] == "NVDA-001"

    # 10. Execution Memory
    memory = ExecutionMemory()
    memory.save({"order": "NVDA", "decision": "VWAP split 20", "result": "filled"})
    memory.save({"order": "AAPL", "decision": "TWAP split 10", "result": "filled"})
    assert len(memory.history) == 2
    assert memory.history[0]["decision"] == "VWAP split 20"

    # 11. Execution Intelligence Service
    service = ExecutionIntelligenceService(trader=trader)
    result = service.execute({"symbol": "TSLA", "side": "BUY", "quantity": 500})
    assert result["execution_plan"]["symbol"] == "TSLA"
