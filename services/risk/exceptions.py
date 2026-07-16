"""
Risk exceptions.
"""

from __future__ import annotations


class RiskRejectedError(RuntimeError):
    """Risk validation failed."""