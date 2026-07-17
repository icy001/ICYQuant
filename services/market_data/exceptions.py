"""
Market data exceptions.
"""

from __future__ import annotations


class QuoteNotFoundError(LookupError):
    """Quote not found."""