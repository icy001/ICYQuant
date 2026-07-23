from services.platform.governance import (
    LifecycleManager,
    AgentStatus,
)


def test_lifecycle():

    manager = LifecycleManager()

    manager.update(
        "research",
        AgentStatus.RUNNING,
    )

    assert manager.get(
        "research"
    ) == AgentStatus.RUNNING