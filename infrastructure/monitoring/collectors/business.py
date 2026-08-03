"""
Business metrics collector.

Provides a framework for collecting
business-level metrics from strategy,
OMS, risk, ledger, and portfolio
modules.

This collector acts as a pluggable
framework where business modules can
register metric callbacks to provide
domain-specific metrics.

Usage:
    from infrastructure.monitoring.collectors import BusinessCollector

    collector = BusinessCollector()

    # Register a strategy metric provider
    def strategy_metrics():
        return {
            "strategy_pnl": 12345.67,
            "strategy_trades": 150,
        }

    collector.register_provider("strategy", strategy_metrics)
    registry.add_collector("business", collector)
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from ..collector import BaseCollector
from ..models import MetricPoint


class BusinessCollector(BaseCollector):
    """
    Business metrics collector.

    Framework for collecting business
    domain metrics from strategy, OMS,
    risk, ledger, and portfolio modules.

    Each business module can register
    a provider callback that returns
    a dictionary of metric name to value
    mappings.

    Metric naming convention:
    - icyquant_business_<domain>_<metric>
      e.g., icyquant_business_strategy_pnl

    Usage:
        collector = BusinessCollector()

        # Strategy metrics
        collector.register_provider(
            "strategy",
            lambda: {"pnl": 12345.67, "trades": 150}
        )

        # OMS metrics
        collector.register_provider(
            "oms",
            lambda: {
                "orders_total": 500,
                "orders_open": 25,
                "orders_filled": 475,
            }
        )

        # Risk metrics
        collector.register_provider(
            "risk",
            lambda: {
                "positions_total": 120,
                "risk_rejects": 3,
                "var_95": 500000.0,
            }
        )
    """

    def __init__(
        self,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize business collector.

        Args:
            labels: Additional labels for all metrics.
        """

        super().__init__(
            name="business",
            namespace="icyquant",
            labels=labels,
        )
        self._providers: Dict[
            str, Callable[[], Dict[str, float]]
        ] = {}
        self._static_metrics: Dict[str, float] = {}

    @property
    def is_available(
        self,
    ) -> bool:
        """Business collector is always available."""
        return True

    def register_provider(
        self,
        domain: str,
        provider: Callable[[], Dict[str, float]],
    ) -> None:
        """
        Register a business metric provider.

        Args:
            domain: Business domain name
                    (strategy, oms, risk, etc.).
            provider: Callback returning dict
                     of metric name to value.
        """

        self._providers[domain] = provider

    def set_metric(
        self,
        name: str,
        value: float,
    ) -> None:
        """
        Set a static business metric.

        For metrics that are updated
        externally rather than via a
        provider callback.

        Args:
            name: Metric name (without prefix).
            value: Metric value.
        """

        self._static_metrics[name] = value

    def remove_provider(
        self,
        domain: str,
    ) -> None:
        """
        Remove a business metric provider.

        Args:
            domain: Business domain to remove.
        """

        self._providers.pop(domain, None)

    async def collect(
        self,
    ) -> List[MetricPoint]:
        """
        Collect business metrics from all providers.

        Returns:
            List of MetricPoint objects.
        """

        points: List[MetricPoint] = []

        # Collect from providers
        for domain, provider in self._providers.items():
            try:
                result = provider()
                if result is None:
                    continue

                for metric_name, value in result.items():
                    full_name = (
                        f"business_{domain}_{metric_name}"
                    )
                    unit = ""
                    if "latency" in metric_name or "duration" in metric_name:
                        unit = "ms"
                    elif "bytes" in metric_name:
                        unit = "bytes"
                    elif "ratio" in metric_name or "rate" in metric_name:
                        unit = ""

                    metric_type = (
                        "counter"
                        if metric_name.endswith("_total")
                        else "gauge"
                    )

                    points.append(
                        self._make_point(
                            full_name,
                            float(value),
                            metric_type=metric_type,
                            unit=unit,
                            extra_labels={
                                "domain": domain
                            },
                        )
                    )
            except Exception:
                continue

        # Collect static metrics
        for name, value in self._static_metrics.items():
            points.append(
                self._make_point(
                    name,
                    float(value),
                    metric_type="gauge",
                    unit="",
                )
            )

        return points

    def get_provider_names(
        self,
    ) -> List[str]:
        """
        Get list of registered provider domains.

        Returns:
            List of domain names.
        """

        return list(self._providers.keys())

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get business collector status.

        Returns:
            Status dictionary.
        """

        return {
            "providers": self.get_provider_names(),
            "static_metrics": len(self._static_metrics),
        }