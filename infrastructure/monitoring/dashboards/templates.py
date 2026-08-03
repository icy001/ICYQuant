"""
Dashboard template library.

Provides pre-built dashboard templates
for all ICYQuant infrastructure and
business modules, covering:
Infrastructure, Database, Redis, Kafka,
Storage, API, Strategy, OMS, Risk,
and Portfolio.

Each template includes PromQL queries
targeting the icyquant_ metric namespace.
"""

from __future__ import annotations

from typing import Dict, List

from ..dashboard_models import (
    DashboardCategory,
    DashboardPanel,
    DashboardTemplate,
    PanelType,
)


def _infrastructure_template() -> DashboardTemplate:
    """Create infrastructure overview dashboard."""

    return DashboardTemplate(
        name="infrastructure",
        title="ICYQuant Infrastructure Overview",
        category=DashboardCategory.INFRASTRUCTURE,
        description="System and infrastructure metrics overview",
        tags=["icyquant", "infrastructure", "overview"],
        panels=[
            DashboardPanel(
                title="CPU Usage",
                type=PanelType.GRAPH,
                queries=["icyquant_cpu_usage_percent"],
                unit="percent",
                grid_pos={"x": 0, "y": 0, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Memory Usage",
                type=PanelType.GRAPH,
                queries=["icyquant_memory_usage_percent"],
                unit="percent",
                grid_pos={"x": 12, "y": 0, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Disk Usage",
                type=PanelType.GAUGE,
                queries=["icyquant_disk_usage_percent"],
                unit="percent",
                grid_pos={"x": 0, "y": 8, "w": 8, "h": 8},
            ),
            DashboardPanel(
                title="Network I/O",
                type=PanelType.GRAPH,
                queries=[
                    "rate(icyquant_network_sent_bytes[5m])",
                    "rate(icyquant_network_received_bytes[5m])",
                ],
                unit="Bps",
                grid_pos={"x": 8, "y": 8, "w": 16, "h": 8},
            ),
            DashboardPanel(
                title="Async Tasks",
                type=PanelType.STAT,
                queries=["icyquant_async_tasks"],
                grid_pos={"x": 0, "y": 16, "w": 6, "h": 4},
            ),
            DashboardPanel(
                title="Python GC",
                type=PanelType.GRAPH,
                queries=["icyquant_python_gc_total"],
                grid_pos={"x": 6, "y": 16, "w": 12, "h": 4},
            ),
        ],
    )


def _database_template() -> DashboardTemplate:
    """Create database monitoring dashboard."""

    return DashboardTemplate(
        name="database",
        title="ICYQuant Database Monitoring",
        category=DashboardCategory.DATABASE,
        description="Database connection pool and query metrics",
        tags=["icyquant", "database"],
        panels=[
            DashboardPanel(
                title="Pool Size",
                type=PanelType.GRAPH,
                queries=["icyquant_database_pool_size"],
                grid_pos={"x": 0, "y": 0, "w": 8, "h": 8},
            ),
            DashboardPanel(
                title="Active Connections",
                type=PanelType.GRAPH,
                queries=["icyquant_database_active_connections"],
                grid_pos={"x": 8, "y": 0, "w": 8, "h": 8},
            ),
            DashboardPanel(
                title="Idle Connections",
                type=PanelType.GRAPH,
                queries=["icyquant_database_idle_connections"],
                grid_pos={"x": 16, "y": 0, "w": 8, "h": 8},
            ),
            DashboardPanel(
                title="Pool Overflow",
                type=PanelType.STAT,
                queries=["icyquant_database_pool_overflow"],
                grid_pos={"x": 0, "y": 8, "w": 6, "h": 4},
            ),
            DashboardPanel(
                title="Database Uptime",
                type=PanelType.STAT,
                queries=["icyquant_database_uptime_seconds"],
                unit="s",
                grid_pos={"x": 6, "y": 8, "w": 6, "h": 4},
            ),
        ],
    )


def _redis_template() -> DashboardTemplate:
    """Create Redis monitoring dashboard."""

    return DashboardTemplate(
        name="redis",
        title="ICYQuant Redis Monitoring",
        category=DashboardCategory.REDIS,
        description="Redis cache and command metrics",
        tags=["icyquant", "redis"],
        panels=[
            DashboardPanel(
                title="Cache Hit Rate",
                type=PanelType.GAUGE,
                queries=["icyquant_redis_cache_hit_ratio"],
                unit="percentunit",
                grid_pos={"x": 0, "y": 0, "w": 8, "h": 8},
                thresholds=[
                    {"color": "red", "value": 0.5},
                    {"color": "yellow", "value": 0.8},
                    {"color": "green", "value": 0.95},
                ],
            ),
            DashboardPanel(
                title="Cache Hits vs Misses",
                type=PanelType.GRAPH,
                queries=[
                    "rate(icyquant_redis_cache_hit_total[5m])",
                    "rate(icyquant_redis_cache_miss_total[5m])",
                ],
                grid_pos={"x": 8, "y": 0, "w": 16, "h": 8},
            ),
            DashboardPanel(
                title="Command Rate",
                type=PanelType.GRAPH,
                queries=[
                    "rate(icyquant_redis_commands_total[5m])"
                ],
                grid_pos={"x": 0, "y": 8, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Failed Commands",
                type=PanelType.STAT,
                queries=["icyquant_redis_failed_total"],
                grid_pos={"x": 12, "y": 8, "w": 6, "h": 4},
            ),
            DashboardPanel(
                title="Avg Latency",
                type=PanelType.STAT,
                queries=["icyquant_redis_latency_ms"],
                unit="ms",
                grid_pos={"x": 18, "y": 8, "w": 6, "h": 4},
            ),
        ],
    )


def _kafka_template() -> DashboardTemplate:
    """Create Kafka monitoring dashboard."""

    return DashboardTemplate(
        name="kafka",
        title="ICYQuant Kafka Monitoring",
        category=DashboardCategory.KAFKA,
        description="Kafka producer and consumer metrics",
        tags=["icyquant", "kafka"],
        panels=[
            DashboardPanel(
                title="Producer Messages",
                type=PanelType.GRAPH,
                queries=[
                    "rate(icyquant_kafka_producer_messages_total[5m])"
                ],
                grid_pos={"x": 0, "y": 0, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Consumer Messages",
                type=PanelType.GRAPH,
                queries=[
                    "rate(icyquant_kafka_consumer_messages_total[5m])"
                ],
                grid_pos={"x": 12, "y": 0, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Failed Messages",
                type=PanelType.GRAPH,
                queries=[
                    "rate(icyquant_kafka_producer_failed_total[5m])",
                    "rate(icyquant_kafka_consumer_failed_total[5m])",
                ],
                grid_pos={"x": 0, "y": 8, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Retries",
                type=PanelType.STAT,
                queries=[
                    "icyquant_kafka_producer_retries_total"
                ],
                grid_pos={"x": 12, "y": 8, "w": 6, "h": 4},
            ),
            DashboardPanel(
                title="Rebalances",
                type=PanelType.STAT,
                queries=[
                    "icyquant_kafka_consumer_rebalance_total"
                ],
                grid_pos={"x": 18, "y": 8, "w": 6, "h": 4},
            ),
        ],
    )


def _storage_template() -> DashboardTemplate:
    """Create storage monitoring dashboard."""

    return DashboardTemplate(
        name="storage",
        title="ICYQuant Storage Monitoring",
        category=DashboardCategory.STORAGE,
        description="Storage operations and cache metrics",
        tags=["icyquant", "storage"],
        panels=[
            DashboardPanel(
                title="Upload Rate",
                type=PanelType.GRAPH,
                queries=[
                    "rate(icyquant_storage_upload_total[5m])"
                ],
                grid_pos={"x": 0, "y": 0, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Download Rate",
                type=PanelType.GRAPH,
                queries=[
                    "rate(icyquant_storage_download_total[5m])"
                ],
                grid_pos={"x": 12, "y": 0, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Cache Hit Rate",
                type=PanelType.GAUGE,
                queries=[
                    "icyquant_storage_cache_hit_ratio"
                ],
                unit="percentunit",
                grid_pos={"x": 0, "y": 8, "w": 8, "h": 8},
            ),
            DashboardPanel(
                title="Bytes Transferred",
                type=PanelType.GRAPH,
                queries=[
                    "rate(icyquant_storage_bytes_uploaded[5m])",
                    "rate(icyquant_storage_bytes_downloaded[5m])",
                ],
                unit="Bps",
                grid_pos={"x": 8, "y": 8, "w": 16, "h": 8},
            ),
        ],
    )


def _api_template() -> DashboardTemplate:
    """Create API monitoring dashboard."""

    return DashboardTemplate(
        name="api",
        title="ICYQuant API Monitoring",
        category=DashboardCategory.API,
        description="HTTP request and error metrics",
        tags=["icyquant", "api", "http"],
        panels=[
            DashboardPanel(
                title="Request Rate",
                type=PanelType.GRAPH,
                queries=[
                    "rate(icyquant_http_requests_total[5m])"
                ],
                grid_pos={"x": 0, "y": 0, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Request Latency",
                type=PanelType.GRAPH,
                queries=[
                    "icyquant_http_request_duration_ms"
                ],
                unit="ms",
                grid_pos={"x": 12, "y": 0, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Error Rate",
                type=PanelType.GRAPH,
                queries=[
                    "rate(icyquant_application_errors_total[5m])"
                ],
                grid_pos={"x": 0, "y": 8, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Active Workers",
                type=PanelType.STAT,
                queries=["icyquant_worker_tasks"],
                grid_pos={"x": 12, "y": 8, "w": 6, "h": 4},
            ),
        ],
    )


def _strategy_template() -> DashboardTemplate:
    """Create strategy monitoring dashboard."""

    return DashboardTemplate(
        name="strategy",
        title="ICYQuant Strategy Monitoring",
        category=DashboardCategory.STRATEGY,
        description="Strategy PnL and trade metrics",
        tags=["icyquant", "strategy", "trading"],
        panels=[
            DashboardPanel(
                title="Strategy PnL",
                type=PanelType.GRAPH,
                queries=[
                    "icyquant_business_strategy_pnl"
                ],
                unit="currencyUSD",
                grid_pos={"x": 0, "y": 0, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Strategy Trades",
                type=PanelType.STAT,
                queries=[
                    "icyquant_business_strategy_trades"
                ],
                grid_pos={"x": 12, "y": 0, "w": 6, "h": 4},
            ),
            DashboardPanel(
                title="Strategy Positions",
                type=PanelType.STAT,
                queries=[
                    "icyquant_business_strategy_positions"
                ],
                grid_pos={"x": 18, "y": 0, "w": 6, "h": 4},
            ),
        ],
    )


def _oms_template() -> DashboardTemplate:
    """Create OMS monitoring dashboard."""

    return DashboardTemplate(
        name="oms",
        title="ICYQuant OMS Monitoring",
        category=DashboardCategory.OMS,
        description="Order management system metrics",
        tags=["icyquant", "oms", "orders"],
        panels=[
            DashboardPanel(
                title="Orders Total",
                type=PanelType.STAT,
                queries=[
                    "icyquant_business_oms_orders_total"
                ],
                grid_pos={"x": 0, "y": 0, "w": 6, "h": 4},
            ),
            DashboardPanel(
                title="Open Orders",
                type=PanelType.STAT,
                queries=[
                    "icyquant_business_oms_orders_open"
                ],
                grid_pos={"x": 6, "y": 0, "w": 6, "h": 4},
            ),
            DashboardPanel(
                title="Filled Orders",
                type=PanelType.STAT,
                queries=[
                    "icyquant_business_oms_orders_filled"
                ],
                grid_pos={"x": 12, "y": 0, "w": 6, "h": 4},
            ),
        ],
    )


def _risk_template() -> DashboardTemplate:
    """Create risk monitoring dashboard."""

    return DashboardTemplate(
        name="risk",
        title="ICYQuant Risk Monitoring",
        category=DashboardCategory.RISK,
        description="Risk metrics and exposure monitoring",
        tags=["icyquant", "risk"],
        panels=[
            DashboardPanel(
                title="VaR (95%)",
                type=PanelType.GRAPH,
                queries=[
                    "icyquant_business_risk_var_95"
                ],
                unit="currencyUSD",
                grid_pos={"x": 0, "y": 0, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Risk Rejects",
                type=PanelType.STAT,
                queries=[
                    "icyquant_business_risk_rejects"
                ],
                grid_pos={"x": 12, "y": 0, "w": 6, "h": 4},
            ),
        ],
    )


def _portfolio_template() -> DashboardTemplate:
    """Create portfolio monitoring dashboard."""

    return DashboardTemplate(
        name="portfolio",
        title="ICYQuant Portfolio Monitoring",
        category=DashboardCategory.PORTFOLIO,
        description="Portfolio value and position metrics",
        tags=["icyquant", "portfolio"],
        panels=[
            DashboardPanel(
                title="Portfolio Value",
                type=PanelType.GRAPH,
                queries=[
                    "icyquant_business_portfolio_value"
                ],
                unit="currencyUSD",
                grid_pos={"x": 0, "y": 0, "w": 12, "h": 8},
            ),
            DashboardPanel(
                title="Position Count",
                type=PanelType.STAT,
                queries=[
                    "icyquant_business_portfolio_positions"
                ],
                grid_pos={"x": 12, "y": 0, "w": 6, "h": 4},
            ),
        ],
    )


# Template registry
DASHBOARD_TEMPLATES: Dict[str, DashboardTemplate] = {
    "infrastructure": _infrastructure_template(),
    "database": _database_template(),
    "redis": _redis_template(),
    "kafka": _kafka_template(),
    "storage": _storage_template(),
    "api": _api_template(),
    "strategy": _strategy_template(),
    "oms": _oms_template(),
    "risk": _risk_template(),
    "portfolio": _portfolio_template(),
}


def get_template(
    name: str,
) -> DashboardTemplate:
    """
    Get a dashboard template by name.

    Args:
        name: Template name.

    Returns:
        DashboardTemplate instance.

    Raises:
        KeyError: If template not found.
    """

    template = DASHBOARD_TEMPLATES.get(name)
    if template is None:
        raise KeyError(
            f"Dashboard template not found: {name}. "
            f"Available: {list(DASHBOARD_TEMPLATES.keys())}"
        )
    return template


def list_templates() -> List[str]:
    """
    List all available template names.

    Returns:
        List of template names.
    """

    return list(DASHBOARD_TEMPLATES.keys())


def all_templates() -> List[DashboardTemplate]:
    """
    Get all dashboard templates.

    Returns:
        List of all DashboardTemplate instances.
    """

    return list(DASHBOARD_TEMPLATES.values())
