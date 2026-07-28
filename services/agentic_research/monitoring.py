"""Continuous monitoring agent for tracking investment thesis changes."""

from __future__ import annotations


class ResearchMonitoringAgent:
    """Continuously monitors tracked securities for material changes.

    Tracks earnings, news, price movements, and macro shifts, alerting
    when the original investment thesis needs to be re-evaluated.
    """

    def monitor(self, symbol: str) -> dict:
        """Monitor a symbol for thesis-affecting changes.

        Args:
            symbol: Ticker symbol to monitor.

        Returns:
            Dict with ``symbol`` and ``status`` keys.
        """
        return {
            "symbol": symbol,
            "status": "tracked",
        }
