"""
Correlation Monitor — Real-time portfolio correlation analysis.

Computes pairwise correlations between portfolio assets, detects
clusters of highly correlated positions, and identifies hidden
concentration risk through correlation structure.

Architecture::

    Portfolio Assets → Correlation Matrix → Cluster Detection → Concentration Risk
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class CorrelationReport:
    """Correlation analysis report for a portfolio."""
    account_id: str
    symbols: list[str] = field(default_factory=list)
    correlation_matrix: dict[str, dict[str, float]] = field(default_factory=dict)
    avg_correlation: float = 0.0
    max_correlation: float = 0.0
    max_correlation_pair: tuple[str, str] = ("", "")
    clusters: dict[str, list[str]] = field(default_factory=dict)
    cluster_count: int = 0
    correlation_risk_score: float = 0.0
    risk_level: str = "LOW"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "symbols": self.symbols,
            "correlation_matrix": {
                s: dict(row) for s, row in self.correlation_matrix.items()
            },
            "avg_correlation": self.avg_correlation,
            "max_correlation": self.max_correlation,
            "max_correlation_pair": list(self.max_correlation_pair),
            "clusters": {k: list(v) for k, v in self.clusters.items()},
            "cluster_count": self.cluster_count,
            "correlation_risk_score": self.correlation_risk_score,
            "risk_level": self.risk_level,
        }


class CorrelationMonitor:
    """
    Real-time portfolio correlation analysis engine.

    Computes pairwise correlations from return series, detects
    clusters of highly correlated assets, and identifies hidden
    concentration risk.

    Usage::

        monitor = CorrelationMonitor()
        await monitor.initialize()

        report = await monitor.analyze("ACC-01", returns_data)
    """

    def __init__(
        self,
        correlation_threshold: float = 0.7,
        cluster_threshold: float = 0.6,
        min_correlation_alert: float = 0.85,
    ) -> None:
        self._correlation_threshold = correlation_threshold
        self._cluster_threshold = cluster_threshold
        self._min_correlation_alert = min_correlation_alert
        self._lock = asyncio.Lock()
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        """Initialize the correlation monitor."""
        self._initialized = True
        logger.info("CorrelationMonitor initialized.")

    async def stop(self) -> None:
        """Stop the correlation monitor."""
        self._initialized = False
        logger.info("CorrelationMonitor stopped.")

    # ---- Core API ----

    async def analyze(
        self,
        account_id: str,
        returns: dict[str, list[float]],
    ) -> CorrelationReport:
        """
        Analyze correlation structure of portfolio assets.

        Args:
            account_id: Account identifier.
            returns: Dict of symbol → list of daily returns (decimal).

        Returns CorrelationReport with matrix, clusters, and risk score.
        """
        symbols = list(returns.keys())

        if len(symbols) < 2:
            return CorrelationReport(
                account_id=account_id,
                symbols=symbols,
                correlation_risk_score=0.0,
                risk_level="LOW",
            )

        # Build correlation matrix
        matrix = await self._compute_correlation_matrix(returns)

        # Compute aggregate stats
        total_corr = 0.0
        max_corr = -1.0
        max_pair = ("", "")
        pair_count = 0

        for i, sym_a in enumerate(symbols):
            for sym_b in symbols[i + 1:]:
                corr = matrix.get(sym_a, {}).get(sym_b, 0.0)
                total_corr += corr
                pair_count += 1
                if corr > max_corr:
                    max_corr = corr
                    max_pair = (sym_a, sym_b)

        avg_corr = total_corr / pair_count if pair_count > 0 else 0.0

        # Cluster detection
        clusters = self._detect_clusters(symbols, matrix)

        # Risk scoring
        risk_score = self._compute_correlation_risk(avg_corr, max_corr, len(clusters), len(symbols))
        risk_level = "LOW"
        if risk_score >= 80:
            risk_level = "CRITICAL"
        elif risk_score >= 60:
            risk_level = "HIGH"
        elif risk_score >= 30:
            risk_level = "MEDIUM"

        return CorrelationReport(
            account_id=account_id,
            symbols=symbols,
            correlation_matrix=matrix,
            avg_correlation=avg_corr,
            max_correlation=max_corr,
            max_correlation_pair=max_pair,
            clusters=clusters,
            cluster_count=len(clusters),
            correlation_risk_score=risk_score,
            risk_level=risk_level,
        )

    async def analyze_pair(
        self,
        symbol_a: str,
        symbol_b: str,
        returns_a: list[float],
        returns_b: list[float],
    ) -> dict[str, Any]:
        """Compute correlation between two symbols."""
        corr = self._pearson_correlation(returns_a, returns_b)

        alert = None
        if abs(corr) > self._min_correlation_alert:
            alert = {
                "severity": "HIGH" if abs(corr) > 0.9 else "MEDIUM",
                "message": f"{symbol_a}-{symbol_b} correlation {corr:.3f} is very high",
            }

        return {
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "correlation": corr,
            "alert": alert,
        }

    async def get_diversification_benefit(
        self,
        returns: dict[str, list[float]],
        weights: dict[str, float],
    ) -> dict[str, Any]:
        """
        Estimate diversification benefit of the portfolio.

        Returns the ratio of weighted-average volatility to portfolio
        volatility (diversification ratio).
        """
        symbols = list(returns.keys())
        if len(symbols) < 2:
            return {"diversification_ratio": 1.0, "benefit": "none"}

        # Portfolio variance = w' Σ w
        matrix = await self._compute_correlation_matrix(returns)

        # Simple approximation: avg correlation
        total_corr = 0.0
        count = 0
        for i, sym_a in enumerate(symbols):
            for sym_b in symbols[i + 1:]:
                total_corr += matrix.get(sym_a, {}).get(sym_b, 0.0)
                count += 1
        avg_corr = total_corr / count if count > 0 else 0.0

        # Diversification ratio = 1 / sqrt(avg_corr) approximation
        div_ratio = 1.0 / max(abs(avg_corr), 0.01) ** 0.5 if avg_corr != 0 else 10.0

        benefit = "high"
        if div_ratio < 1.2:
            benefit = "none"
        elif div_ratio < 1.5:
            benefit = "low"
        elif div_ratio < 2.0:
            benefit = "moderate"

        return {
            "diversification_ratio": div_ratio,
            "avg_correlation": avg_corr,
            "benefit": benefit,
        }

    # ---- Internal ----

    async def _compute_correlation_matrix(
        self,
        returns: dict[str, list[float]],
    ) -> dict[str, dict[str, float]]:
        """Compute pairwise Pearson correlation matrix."""
        symbols = list(returns.keys())
        matrix: dict[str, dict[str, float]] = defaultdict(dict)

        for i, sym_a in enumerate(symbols):
            for sym_b in symbols[i:]:
                ret_a = returns[sym_a]
                ret_b = returns[sym_b]
                corr = self._pearson_correlation(ret_a, ret_b)
                matrix[sym_a][sym_b] = corr
                if sym_a != sym_b:
                    matrix[sym_b][sym_a] = corr

        return dict(matrix)

    def _pearson_correlation(self, x: list[float], y: list[float]) -> float:
        """Compute Pearson correlation coefficient."""
        n = min(len(x), len(y))
        if n < 2:
            return 0.0

        x_arr = x[-n:]
        y_arr = y[-n:]

        mean_x = sum(x_arr) / n
        mean_y = sum(y_arr) / n

        cov = sum((x_arr[i] - mean_x) * (y_arr[i] - mean_y) for i in range(n))
        std_x = (sum((v - mean_x) ** 2 for v in x_arr)) ** 0.5
        std_y = (sum((v - mean_y) ** 2 for v in y_arr)) ** 0.5

        if std_x == 0 or std_y == 0:
            return 0.0

        return cov / (std_x * std_y)

    def _detect_clusters(
        self,
        symbols: list[str],
        matrix: dict[str, dict[str, float]],
    ) -> dict[str, list[str]]:
        """Simple cluster detection using threshold-based grouping."""
        visited: set[str] = set()
        clusters: dict[str, list[str]] = {}

        for symbol in symbols:
            if symbol in visited:
                continue

            cluster: list[str] = [symbol]
            visited.add(symbol)

            # Find all symbols correlated above threshold
            for other in symbols:
                if other in visited:
                    continue
                corr = matrix.get(symbol, {}).get(other, 0.0)
                if corr > self._cluster_threshold:
                    cluster.append(other)
                    visited.add(other)

            if len(cluster) > 1:
                cluster_name = f"cluster_{len(clusters) + 1}"
                clusters[cluster_name] = cluster

        return clusters

    def _compute_correlation_risk(
        self,
        avg_corr: float,
        max_corr: float,
        num_clusters: int,
        num_symbols: int,
    ) -> float:
        """Compute correlation risk score."""
        score = 0.0

        # Average correlation: 40% weight
        if avg_corr > 0.7:
            score += 40
        elif avg_corr > 0.5:
            score += 25
        elif avg_corr > 0.3:
            score += 10

        # Max correlation: 35% weight
        if max_corr > 0.9:
            score += 35
        elif max_corr > 0.75:
            score += 20
        elif max_corr > 0.5:
            score += 10

        # Cluster concentration: 25% weight
        if num_symbols > 0 and num_clusters > 0:
            cluster_ratio = num_clusters / num_symbols
            if cluster_ratio < 0.2:  # Very few clusters = concentrated
                score += 25
            elif cluster_ratio < 0.4:
                score += 15
            elif cluster_ratio < 0.6:
                score += 5

        return min(score, 100.0)

    # ---- Stats ----

    async def get_stats(self) -> dict[str, Any]:
        """Get monitor statistics."""
        return {
            "correlation_threshold": self._correlation_threshold,
            "cluster_threshold": self._cluster_threshold,
            "min_correlation_alert": self._min_correlation_alert,
        }

    async def health_check(self) -> dict[str, Any]:
        """Check monitor health."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
        }
