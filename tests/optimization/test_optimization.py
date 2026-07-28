from services.optimization import *


def test_portfolio_optimizer():
    service = OptimizationService(
        OptimizationManager(
            AllocationEngine(),
            PortfolioRepository()
        )
    )

    request = AllocationRequest(
        "PORT001",
        [
            "NVDA",
            "GLD"
        ]
    )

    result = service.optimize(request)

    assert len(result.weights) == 2