"""
Portfolio serializer.
"""

from __future__ import annotations

from dataclasses import asdict

from .model import Portfolio


class PortfolioSerializer:
    def to_dict(
        self,
        portfolio: Portfolio,
    ) -> dict:
        return asdict(portfolio)