"""Tests for AI Agentic Research Platform."""

from services.agentic_research import (
    AgenticResearchService,
    FinancialAnalysisAgent,
    IndustryAnalysisAgent,
    InvestmentThesisEngine,
    ResearchAgent,
    ResearchAgentRegistry,
    ResearchMemory,
    ResearchMonitoringAgent,
    ResearchQualityEvaluator,
    ResearchReportGenerator,
    ResearchTaskPlanner,
    ValuationAgent,
)


def test_research_planner():
    planner = ResearchTaskPlanner()
    tasks = planner.plan("NVDA")
    assert "financial" in tasks
    assert tasks == ["financial", "industry", "valuation", "risk"]


def test_research_agent_registry():
    registry = ResearchAgentRegistry()
    agent = ResearchAgent(
        id="financial_1",
        role="financial",
        capability=["revenue", "eps", "cash_flow"],
    )
    registry.register(agent)
    agents = registry.list()
    assert len(agents) == 1
    assert agents[0].id == "financial_1"


def test_research_agent_registry_multiple():
    registry = ResearchAgentRegistry()
    registry.register(ResearchAgent(id="fa", role="financial", capability=["revenue"]))
    registry.register(ResearchAgent(id="ia", role="industry", capability=["supply_chain"]))
    registry.register(ResearchAgent(id="va", role="valuation", capability=["dcf"]))
    assert len(registry.list()) == 3


def test_financial_analysis_agent():
    agent = FinancialAnalysisAgent()
    result = agent.analyze("NVDA")
    assert result == {"company": "NVDA", "score": 0.8}


def test_industry_analysis_agent():
    agent = IndustryAnalysisAgent()
    result = agent.analyze("Semiconductors")
    assert result == {"industry": "Semiconductors", "trend": "positive"}


def test_valuation_agent():
    agent = ValuationAgent()
    result = agent.evaluate("NVDA")
    assert result == {"symbol": "NVDA", "valuation": "fair"}


def test_investment_thesis_engine():
    engine = InvestmentThesisEngine()
    data = {"financial": {"score": 0.8}, "industry": {"trend": "positive"}}
    result = engine.build(data)
    assert result == {"thesis": data}


def test_research_report_generator():
    generator = ResearchReportGenerator()
    thesis = {"thesis": {"bull_case": "growth"}}
    result = generator.generate(thesis)
    assert result == {"report": thesis}


def test_research_monitoring_agent():
    agent = ResearchMonitoringAgent()
    result = agent.monitor("NVDA")
    assert result == {"symbol": "NVDA", "status": "tracked"}


def test_research_quality_evaluator():
    evaluator = ResearchQualityEvaluator()
    result = evaluator.evaluate({})
    assert result == {"quality": 1.0}


def test_research_memory():
    memory = ResearchMemory()
    memory.save({"symbol": "NVDA", "thesis": "bullish"})
    memory.save({"symbol": "AMD", "thesis": "neutral"})
    assert len(memory.history) == 2
    assert memory.history[0]["symbol"] == "NVDA"


def test_agentic_research_service():
    planner = ResearchTaskPlanner()
    service = AgenticResearchService(planner)
    result = service.research("NVDA")
    assert "financial" in result
    assert "risk" in result
