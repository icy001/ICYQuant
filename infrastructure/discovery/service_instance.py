"""
Service instance definition.
"""

from dataclasses import dataclass


@dataclass
class ServiceInstance:

    name: str

    host: str

    port: int

    status: str = "healthy"