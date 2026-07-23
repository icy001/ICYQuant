from services.platform.research import (
    ResearchAnalystAgent,
)


def test_research_agent():

    agent = ResearchAnalystAgent()

    result = agent.analyze(
        "NVDA",
        {"revenue": "growth"},
    )

    assert result["company"] == "NVDA"