"""
Dashboard data models.

Defines the core data structures for
dashboard management, including dashboard
definitions, panels, and templates.

These models are used by GrafanaDashboard
and DashboardProvisioner to generate
Grafana-compatible dashboard configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DashboardCategory(str, Enum):
    """
    Dashboard category classification.

    Organizes dashboards by domain
    for logical grouping in Grafana.
    """

    INFRASTRUCTURE = "infrastructure"
    DATABASE = "database"
    REDIS = "redis"
    KAFKA = "kafka"
    STORAGE = "storage"
    API = "api"
    STRATEGY = "strategy"
    OMS = "oms"
    RISK = "risk"
    PORTFOLIO = "portfolio"
    SYSTEM = "system"
    APPLICATION = "application"


class PanelType(str, Enum):
    """
    Grafana panel types.

    Supported visualization types
    for dashboard panels.
    """

    GRAPH = "graph"
    STAT = "stat"
    TABLE = "table"
    HEATMAP = "heatmap"
    GAUGE = "gauge"
    BAR_GAUGE = "bargauge"
    TIMESERIES = "timeseries"


@dataclass
class DashboardPanel:
    """
    A single dashboard panel.

    Represents a Grafana panel with
    PromQL queries and visualization
    settings.

    Attributes:
        title: Panel title.
        type: Panel visualization type.
        queries: List of PromQL queries.
        unit: Value unit (bytes, seconds, etc.).
        datasource: Grafana datasource name.
        grid_pos: Grid position {x, y, w, h}.
        thresholds: Panel thresholds.
    """

    title: str
    type: PanelType = PanelType.GRAPH
    queries: List[str] = field(default_factory=list)
    unit: str = ""
    datasource: str = "Prometheus"
    grid_pos: Dict[str, int] = field(
        default_factory=lambda: {
            "x": 0,
            "y": 0,
            "w": 12,
            "h": 8,
        }
    )
    thresholds: List[Dict[str, Any]] = field(
        default_factory=list
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Convert to Grafana panel dict.

        Returns:
            Grafana-compatible panel dictionary.
        """

        return {
            "title": self.title,
            "type": self.type.value,
            "datasource": self.datasource,
            "gridPos": self.grid_pos,
            "unit": self.unit,
            "targets": [
                {
                    "expr": q,
                    "legendFormat": q.split("{")[0]
                    if "{" in q
                    else q,
                }
                for q in self.queries
            ],
            "thresholds": {
                "steps": self.thresholds,
            },
        }


@dataclass
class DashboardTemplate:
    """
    A dashboard template definition.

    Defines a complete dashboard with
    panels, variables, and metadata
    that can be provisioned to Grafana.

    Attributes:
        name: Dashboard name.
        title: Display title.
        category: Dashboard category.
        description: Dashboard description.
        panels: List of panels.
        tags: Dashboard tags.
        refresh: Refresh interval.
        time_range: Default time range.
    """

    name: str
    title: str
    category: DashboardCategory = (
        DashboardCategory.INFRASTRUCTURE
    )
    description: str = ""
    panels: List[DashboardPanel] = field(
        default_factory=list
    )
    tags: List[str] = field(default_factory=list)
    refresh: str = "30s"
    time_range: str = "1h"

    def to_dict(
        self,
    ) -> Dict[str, Any]:
        """
        Convert to Grafana dashboard dict.

        Returns:
            Grafana-compatible dashboard dictionary.
        """

        return {
            "title": self.title,
            "description": self.description,
            "tags": self.tags,
            "refresh": self.refresh,
            "time": {"from": f"now-{self.time_range}"},
            "panels": [p.to_dict() for p in self.panels],
            "schemaVersion": 27,
            "version": 1,
        }
