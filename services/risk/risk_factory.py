"""
Risk factory.
"""

from .risk_domain import RiskDomain


class RiskFactory:

    def create(
        self,
        domain_id,
    ):

        return RiskDomain(
            domain_id=domain_id,
            name="Risk",
            version="0.3.0-beta3",
            status="ACTIVE",
        )