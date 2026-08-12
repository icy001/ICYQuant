"""
Command errors — raised when a control command cannot be created, approved or
executed (spec section 6).
"""

from __future__ import annotations


class CommandError(Exception):
    """Base error for incident command operations."""


class CommandRejectedError(CommandError):
    """Raised when a command type is not allowed for the incident severity."""


class CommandApprovalError(CommandError):
    """Raised when a command cannot be approved (e.g. it is not PENDING)."""
