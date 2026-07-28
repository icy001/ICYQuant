"""Portfolio Graph – maps portfolio → position → asset → risk → factor relationships."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from .graph_builder import GraphBuilder


class PortfolioGraph:
    """Builds the portfolio knowledge graph connecting portfolios, positions,
    assets, risks, and factors into a unified view."""

    def __init__(self) -> None:
        self._graph: GraphBuilder = GraphBuilder()

    def connect(self, portfolio: str, asset: str) -> Dict[str, str]:
        """Connect a portfolio to an asset.

        Args:
            portfolio: portfolio entity id.
            asset: asset entity id.

        Returns:
            Dict with portfolio and asset ids.
        """
        self._graph.add_edge(portfolio, asset, "holds", 1.0)
        return {"portfolio": portfolio, "asset": asset}

    def add_position(
        self,
        portfolio_id: str,
        asset_id: str,
        quantity: float = 1.0,
        weight: float = 0.0,
    ) -> None:
        """Add a position (portfolio holds asset)."""
        self._graph.add_edge(portfolio_id, asset_id, "holds", weight if weight > 0 else quantity)

    def add_risk_exposure(
        self,
        asset_id: str,
        risk_type: str,
        exposure: float,
    ) -> None:
        """Link an asset to a risk factor."""
        self._graph.add_edge(asset_id, risk_type, "exposed_to", exposure)

    def add_factor_exposure(
        self,
        asset_id: str,
        factor_id: str,
        beta: float,
    ) -> None:
        """Link an asset to a factor with beta weight."""
        self._graph.add_edge(asset_id, factor_id, "driven_by", beta)

    def get_holdings(self, portfolio_id: str) -> List[Tuple[str, float]]:
        """Return all holdings (asset, weight) for a portfolio."""
        return [(e[1], e[3]) for e in self._graph.edges if e[0] == portfolio_id and e[2] == "holds"]

    def get_risks(self, asset_id: str) -> List[Tuple[str, float]]:
        """Return all risk exposures for an asset."""
        return [(e[1], e[3]) for e in self._graph.edges if e[0] == asset_id and e[2] == "exposed_to"]

    def get_factors(self, asset_id: str) -> List[Tuple[str, float]]:
        """Return all factor loadings for an asset."""
        return [(e[1], e[3]) for e in self._graph.edges if e[0] == asset_id and e[2] == "driven_by"]

    def aggregate_portfolio_risk(self, portfolio_id: str) -> Dict[str, float]:
        """Aggregate risk exposures across all holdings in a portfolio."""
        risk_totals: Dict[str, float] = {}
        for asset, weight in self.get_holdings(portfolio_id):
            for risk, exposure in self.get_risks(asset):
                risk_totals[risk] = risk_totals.get(risk, 0.0) + exposure * weight
        return risk_totals

    def aggregate_portfolio_factors(self, portfolio_id: str) -> Dict[str, float]:
        """Aggregate factor exposures across all holdings in a portfolio."""
        factor_totals: Dict[str, float] = {}
        for asset, weight in self.get_holdings(portfolio_id):
            for factor, beta in self.get_factors(asset):
                factor_totals[factor] = factor_totals.get(factor, 0.0) + beta * weight
        return factor_totals

    def get_connected_assets(self, portfolio_id: str) -> List[str]:
        """Return all asset ids in a portfolio."""
        return [h[0] for h in self.get_holdings(portfolio_id)]

    def clear(self) -> None:
        self._graph = GraphBuilder()
