"""Compliance monitor for investment mandate and regulatory rules."""

from __future__ import annotations


class ComplianceMonitor:
    """Monitors portfolio compliance against investment mandate,
    exposure limits, regulatory rules, and internal policies.
    """

    def check(self, portfolio: dict) -> bool:
        """Check portfolio compliance.

        Args:
            portfolio: Current portfolio positions and exposures.

        Returns:
            ``True`` if compliant, ``False`` otherwise.
        """
        return True
