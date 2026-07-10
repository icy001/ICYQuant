"""
API dependency providers.
"""

from services.reconciliation import (
    ReconciliationEngine,
)


from .database import (
    get_database_session,
)


_engine = ReconciliationEngine()


def get_reconciliation_engine():
    return _engine


__all__ = [
    "get_database_session",
    "get_reconciliation_engine",
]