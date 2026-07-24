from services.platform.reasoning import (
    Goal,
    GoalManager,
)


def test_goal_manager():

    manager = GoalManager()

    manager.register(
        Goal(
            "goal-1",
            "Analyze NVDA",
        )
    )

    assert manager.get(
        "goal-1"
    ).description == "Analyze NVDA"