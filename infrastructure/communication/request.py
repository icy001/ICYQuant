"""
Service request model.
"""

from dataclasses import dataclass


@dataclass
class ServiceRequest:

    service: str

    action: str

    payload: dict