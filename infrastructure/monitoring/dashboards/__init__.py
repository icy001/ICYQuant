"""
Dashboard management components.

Provides Grafana dashboard generation and
provisioning capabilities for the ICYQuant
monitoring platform.

Includes:
- DashboardTemplate library (10 built-in templates)
- GrafanaDashboard generator
- DashboardProvisioner for automated deployment

Usage:
    from infrastructure.monitoring.dashboards import (
        GrafanaDashboard,
        DashboardProvisioner,
        get_template,
        list_templates,
    )

    generator = GrafanaDashboard()
    dashboard = generator.generate("infrastructure")
"""

from .grafana import GrafanaDashboard
from .provisioning import DashboardProvisioner
from .templates import (
    DASHBOARD_TEMPLATES,
    all_templates,
    get_template,
    list_templates,
)

__all__ = [
    # Generator
    "GrafanaDashboard",
    # Provisioner
    "DashboardProvisioner",
    # Templates
    "DASHBOARD_TEMPLATES",
    "get_template",
    "list_templates",
    "all_templates",
]
