from services.ai import (
    PromptEngine,
    PromptTemplate,
)


def test_prompt_render():

    engine = PromptEngine()

    template = PromptTemplate(
        "P001",
        "Market Analyst",
        "Analyze {{symbol}}",
    )

    result = engine.render(
        template,
        {
            "symbol": "NVDA"
        }
    )

    assert result == "Analyze NVDA"