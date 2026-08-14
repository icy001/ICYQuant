"""Portfolio performance analytics (Commit 35).

Provides the portfolio-level performance domain:

.. code-block:: text

    Beginning Equity
           + External Cash Flow
           + Internal PnL
        = Ending Equity

Plus period-level TWR / MWR analytics, benchmark comparison, relative
performance (active return), risk-adjusted performance metrics and
rolling window analytics.
"""

from .benchmark import (
    BenchmarkObservation,
    BenchmarkPerformanceCalculator,
    RelativePerformance,
)
from .calculator import (
    PortfolioPerformanceCalculator,
)
from .models import (
    PortfolioPerformanceInput,
    PortfolioPerformanceResult,
    PortfolioPeriodPerformance,
    PortfolioBenchmarkPerformance,
    PortfolioRiskMetrics,
)
from .returns import (
    PortfolioReturnCalculator,
)
from .risk_metrics import (
    RiskAdjustedPerformanceCalculator,
)
from .rolling import (
    RollingPerformanceCalculator,
    RollingPerformanceResult,
)
from .service import (
    PortfolioPerformanceService,
)

__all__ = [
    "BenchmarkObservation",
    "BenchmarkPerformanceCalculator",
    "RelativePerformance",

    "PortfolioPerformanceCalculator",
    "PortfolioPerformanceInput",
    "PortfolioPerformanceResult",
    "PortfolioPeriodPerformance",
    "PortfolioBenchmarkPerformance",
    "PortfolioRiskMetrics",

    "PortfolioReturnCalculator",

    "RiskAdjustedPerformanceCalculator",

    "RollingPerformanceCalculator",
    "RollingPerformanceResult",

    "PortfolioPerformanceService",
]
