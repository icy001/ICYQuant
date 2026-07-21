from datetime import datetime

from services.portfolio import (
    PortfolioState,
    PortfolioStateManager,
    StateRepository,
    StateValidator,
)


def test_state_persist():
    repository = StateRepository()

    manager = PortfolioStateManager(
        repository,
        StateValidator(),
    )

    state = PortfolioState(
        state_id="STATE-001",
        portfolio_id="PORT-001",
        version=1,
        updated_at=datetime.utcnow(),
        data={"cash": 500000},
    )

    manager.persist(
        state,
    )

    assert repository.load(
        "PORT-001"
    ) == state