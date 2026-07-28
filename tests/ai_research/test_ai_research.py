from services.ai_research import *


def test_ai_research():

    agent = ResearchAgent()

    repo = ResearchRepository()

    service = AIResearchService(

        agent,

        repo

    )

    request = ResearchRequest(

        "Analyze NVDA momentum",

        {}

    )

    result = service.research(
        request
    )

    assert "analysis" in result
