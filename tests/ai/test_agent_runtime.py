from services.ai import (
    AgentPlanner,
    AgentRuntime,
)


def test_agent_runtime():

    runtime = AgentRuntime(
        AgentPlanner(),
        None,
    )

    result = runtime.run(
        "Analyze market"
    )

    assert result[0]["action"] == "Analyze market"