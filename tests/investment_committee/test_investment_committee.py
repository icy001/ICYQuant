"""Tests for AI Autonomous Investment Committee Engine."""

from services.investment_committee import (
    BearAgent,
    BullAgent,
    CommitteeMember,
    CommitteeMemory,
    DebateEngine,
    InvestmentCommitteeService,
    InvestmentProposal,
    PortfolioManagerAgent,
    ResearchChallengeAgent,
    RiskCommitteeAgent,
    VotingSystem,
)


def test_committee_vote():
    service = InvestmentCommitteeService(VotingSystem())
    result = service.decide(["BUY", "BUY"])
    assert result["decision"] == "APPROVED"


def test_committee_vote_mixed():
    service = InvestmentCommitteeService(VotingSystem())
    result = service.decide(["BUY", "REDUCE", "BUY"])
    assert result["decision"] == "APPROVED"


def test_committee_member():
    member = CommitteeMember(
        id="bull_1",
        role="bull_analyst",
        weight=0.3,
    )
    assert member.id == "bull_1"
    assert member.role == "bull_analyst"
    assert member.weight == 0.3


def test_investment_proposal():
    proposal = InvestmentProposal()
    thesis = {"financial": {"score": 0.8}, "industry": {"trend": "positive"}}
    result = proposal.create("NVDA", thesis)
    assert result["symbol"] == "NVDA"
    assert result["thesis"] == thesis


def test_bull_agent():
    agent = BullAgent()
    result = agent.analyze({"symbol": "NVDA", "thesis": {"score": 0.8}})
    assert result["side"] == "BUY"
    assert result["reason"] == "growth"


def test_bear_agent():
    agent = BearAgent()
    result = agent.analyze({"symbol": "NVDA", "thesis": {"score": 0.8}})
    assert result["side"] == "SELL"
    assert result["reason"] == "risk"


def test_research_challenge_agent():
    agent = ResearchChallengeAgent()
    arg = {"side": "BUY", "reason": "growth"}
    result = agent.challenge(arg)
    assert result["challenge"] == arg


def test_debate_engine():
    engine = DebateEngine()
    arguments = {
        "bull": {"side": "BUY", "reason": "growth"},
        "bear": {"side": "SELL", "reason": "risk"},
    }
    result = engine.debate(arguments)
    assert result == arguments


def test_risk_committee_agent():
    agent = RiskCommitteeAgent()
    result = agent.review({"symbol": "NVDA"})
    assert result["risk"] == "acceptable"


def test_portfolio_manager_agent():
    agent = PortfolioManagerAgent()
    result = agent.review({"symbol": "NVDA"})
    assert result["allocation"] == 0.05


def test_committee_memory():
    memory = CommitteeMemory()
    memory.save({"symbol": "NVDA", "decision": "APPROVED"})
    memory.save({"symbol": "AMD", "decision": "REJECTED"})
    assert len(memory.records) == 2
    assert memory.records[0]["symbol"] == "NVDA"
