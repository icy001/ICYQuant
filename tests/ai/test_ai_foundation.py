from services.ai import (
    PromptRegistry,
    PromptTemplate,
)


def test_prompt_registry():

    registry = PromptRegistry()

    registry.register(
        PromptTemplate(
            "P001",
            "Trading Analyst",
            "Analyze market",
        )
    )

    assert registry.get(
        "P001"
    ).name == "Trading Analyst"