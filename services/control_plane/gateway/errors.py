"""
Gateway errors — raised when the Institutional Control Gateway itself is
misused or cannot perform its duty (spec section 18).
"""

from __future__ import annotations


class GatewayError(Exception):
    """Base error for institutional control gateway operations."""


class ControlEvaluationError(GatewayError):
    """Raised when control evaluation cannot complete because an underlying
    subsystem (e.g. the control registry) is unavailable."""
