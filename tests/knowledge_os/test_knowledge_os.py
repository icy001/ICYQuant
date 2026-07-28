from services.knowledge_os import *


def test_knowledge():
    assistant = KnowledgeAssistant()
    result = assistant.answer("market analysis")
    assert result["answer"] == "market analysis"


def test_knowledge_base_add():
    base = KnowledgeBase()
    result = base.add("factor_analysis_2024")
    assert result == {"knowledge": "factor_analysis_2024"}


def test_research_memory():
    memory = ResearchMemory()
    result = memory.save({"idea": "momentum_reversal", "result": "sharpe_1.5"})
    assert result == {"saved": {"idea": "momentum_reversal", "result": "sharpe_1.5"}}


def test_decision_memory():
    memory = DecisionMemory()
    result = memory.record({"action": "buy_NVDA", "reason": "earnings_surprise", "date": "2024-Q3"})
    assert result == {"decision": {"action": "buy_NVDA", "reason": "earnings_surprise", "date": "2024-Q3"}}


def test_document_intelligence():
    doc_ai = DocumentIntelligence()
    result = doc_ai.analyze("quarterly_report_NVDA.pdf")
    assert result == {"analysis": "quarterly_report_NVDA.pdf"}


def test_knowledge_graph():
    graph = KnowledgeGraph()
    result = graph.connect("NVDA", "AI_Semiconductor")
    assert result == {"relation": ("NVDA", "AI_Semiconductor")}


def test_knowledge_assistant():
    assistant = KnowledgeAssistant()
    result = assistant.answer("What is the risk of NVDA?")
    assert result == {"answer": "What is the risk of NVDA?"}


def test_policy_knowledge():
    manager = PolicyKnowledgeManager()
    result = manager.register("max_position_10pct")
    assert result == {"policy": "max_position_10pct"}


def test_knowledge_search():
    engine = KnowledgeSearchEngine()
    result = engine.search("momentum factor 2024")
    assert result == {"query": "momentum factor 2024"}


def test_knowledge_quality():
    engine = KnowledgeQualityEngine()
    result = engine.evaluate("research_paper_001")
    assert result == {"score": 100}


def test_knowledge_memory():
    memory = KnowledgeMemory()
    assert memory.records == []
    memory.save({"type": "research", "topic": "factor_analysis"})
    memory.save({"type": "decision", "action": "buy_AAPL"})
    assert len(memory.records) == 2
    assert memory.records[0]["type"] == "research"
    assert memory.records[1]["type"] == "decision"


def test_knowledge_operating_service():
    assistant = KnowledgeAssistant()
    service = KnowledgeOperatingService(assistant=assistant)
    result = service.ask("market outlook 2025")
    assert result == {"answer": "market outlook 2025"}


def test_full_knowledge_os_workflow():
    """End-to-end knowledge operating system workflow."""
    # 1. Add to knowledge base
    kb = KnowledgeBase()
    research = kb.add("AI_ETF_strategy_research")
    assert research["knowledge"] == "AI_ETF_strategy_research"

    # 2. Save research memory
    research_mem = ResearchMemory()
    saved = research_mem.save({"idea": "mean_reversion_vol", "status": "backtesting"})
    assert saved["saved"]["idea"] == "mean_reversion_vol"

    # 3. Record investment decision
    decision_mem = DecisionMemory()
    decision = decision_mem.record({
        "stock": "AMD",
        "action": "buy",
        "reason": "data_center_growth",
        "committee_vote": "5-2",
    })
    assert decision["decision"]["stock"] == "AMD"

    # 4. Analyze document
    doc_ai = DocumentIntelligence()
    analysis = doc_ai.analyze("chip_industry_report_2024.pdf")
    assert analysis["analysis"] == "chip_industry_report_2024.pdf"

    # 5. Build knowledge graph
    graph = KnowledgeGraph()
    relation = graph.connect("Semiconductor_Cycle", "NVDA_Revenue")
    assert relation["relation"] == ("Semiconductor_Cycle", "NVDA_Revenue")

    # 6. Ask AI assistant
    assistant = KnowledgeAssistant()
    answer = assistant.answer("How does AI CapEx affect semiconductor stocks?")
    assert answer["answer"] == "How does AI CapEx affect semiconductor stocks?"

    # 7. Register policy
    policy_mgr = PolicyKnowledgeManager()
    policy = policy_mgr.register("sector_exposure_limit_20pct")
    assert policy["policy"] == "sector_exposure_limit_20pct"

    # 8. Semantic search
    search = KnowledgeSearchEngine()
    results = search.search("mean reversion strategy backtest")
    assert results["query"] == "mean reversion strategy backtest"

    # 9. Evaluate knowledge quality
    quality = KnowledgeQualityEngine()
    score = quality.evaluate("investment_thesis_2024")
    assert score["score"] == 100

    # 10. Save to knowledge memory
    memory = KnowledgeMemory()
    memory.save({"event": "research_completed", "topic": "AI_cycle"})
    memory.save({"event": "decision_made", "action": "buy_NVDA"})
    memory.save({"event": "policy_updated", "rule": "max_leverage_2x"})
    assert len(memory.records) == 3

    # 11. Knowledge operating service
    service = KnowledgeOperatingService(assistant=assistant)
    response = service.ask("sector rotation strategy 2025")
    assert response["answer"] == "sector rotation strategy 2025"
