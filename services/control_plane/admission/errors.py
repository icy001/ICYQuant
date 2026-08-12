"""
Admission errors — raised when Order Admission is misused or an underlying
subsystem is missing (spec sections 6 and 16).
"""

from __future__ import annotations


class AdmissionError(Exception):
    """Base error for order admission operations."""


class InvalidAdmissionRequestError(AdmissionError):
    """Raised when a non-OrderAdmissionRequest is passed to the service."""


class RiskEngineUnavailableError(AdmissionError):
    """Raised when the risk engine cannot be evaluated."""


class ControlGatewayUnavailableError(AdmissionError):
    """Raised when the control gateway cannot be evaluated."""
