"""Strategy performance attribution (Commit 34).

Provides the full attribution domain:

.. code-block:: text

    Daily Attribution Engine
              ↓
    Cumulative / Period Report
              ↓
    Repository + Query Layer
"""

from .engine import AttributionEngine
from .models import AttributionInput, AttributionResult
from .query import (
    AttributionQuery,
    AttributionQueryService,
)
from .report import (
    AttributionPeriodReport,
    AttributionReportBuilder,
)
from .repository import AttributionRepository
from .service import AttributionService

__all__ = [
    "AttributionEngine",
    "AttributionInput",
    "AttributionResult",
    "AttributionQuery",
    "AttributionQueryService",
    "AttributionPeriodReport",
    "AttributionReportBuilder",
    "AttributionRepository",
    "AttributionService",
]
