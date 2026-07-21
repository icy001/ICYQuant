from services.portfolio import (
    PortfolioMetrics,
    TraceContext,
)


def test_metrics():
    metrics = PortfolioMetrics()

    result = metrics.collect(
        "portfolio.nav",
        1000000,
    )

    assert result["metric"] == "portfolio.nav"


def test_trace():
    trace = TraceContext()

    assert trace.create()