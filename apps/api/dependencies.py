"""
Dependency container.

Provides application services.
"""

from services.reconciliation import (
    ReconciliationEngine,
)


_engine = ReconciliationEngine()


def get_reconciliation_engine():
    return _engine