"""
Trade exceptions.
"""

from __future__ import annotations


class DuplicateExecutionError(
    RuntimeError,
):
    """
    Duplicate execution report.
    """