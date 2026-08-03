"""
Grafana dashboard generator.

Generates Grafana-compatible dashboard
JSON from DashboardTemplate definitions,
supporting panel layout, PromQL queries,
and datasource configuration.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..dashboard_models import (
    DashboardCategory,
    DashboardPanel,
    DashboardTemplate,
    PanelType,
)
from .templates import (
    DASHBOARD_TEMPLATES,
    all_templates,
    get_template,
    list_templates,
)


class GrafanaDashboard:
    """
    Grafana dashboard generator.

    Converts DashboardTemplate definitions
    into Grafana-compatible JSON dashboards
    with proper panel layouts, PromQL queries,
    and datasource configuration.

    Usage:
        generator = GrafanaDashboard(
            datasource="Prometheus",
            folder="ICYQuant",
        )

        # Generate from template
        dashboard = generator.generate("infrastructure")

        # Generate all
        dashboards = generator.generate_all()
    """

    def __init__(
        self,
        datasource: str = "Prometheus",
        folder: str = "ICYQuant",
        uid_prefix: str = "icyquant",
    ) -> None:
        """
        Initialize Grafana dashboard generator.

        Args:
            datasource: Grafana datasource name.
            folder: Target Grafana folder.
            uid_prefix: Dashboard UID prefix.
        """

        self._datasource = datasource
        self._folder = folder
        self._uid_prefix = uid_prefix

    @property
    def datasource(
        self,
    ) -> str:
        """Get datasource name."""
        return self._datasource

    @property
    def folder(
        self,
    ) -> str:
        """Get folder name."""
        return self._folder

    def generate(
        self,
        template: str,
    ) -> Dict[str, Any]:
        """
        Generate a Grafana dashboard from template.

        Args:
            template: Template name.

        Returns:
            Grafana dashboard JSON dict.
        """

        tpl = get_template(template)

        panels = []
        for i, panel in enumerate(tpl.panels):
            panel_dict = panel.to_dict()
            panel_dict["id"] = i + 1
            panel_dict["datasource"] = self._datasource
            if panel_dict.get("targets"):
                for target in panel_dict["targets"]:
                    target["datasource"] = self._datasource
            panels.append(panel_dict)

        dashboard = {
            "uid": f"{self._uid_prefix}_{tpl.name}",
            "title": tpl.title,
            "description": tpl.description,
            "tags": tpl.tags,
            "refresh": tpl.refresh,
            "time": {"from": f"now-{tpl.time_range}"},
            "panels": panels,
            "schemaVersion": 27,
            "version": 1,
            "folderTitle": self._folder,
        }

        return dashboard

    def generate_all(
        self,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate all dashboards from all templates.

        Returns:
            Dict mapping template name to dashboard dict.
        """

        return {
            name: self.generate(name)
            for name in list_templates()
        }

    def generate_json(
        self,
        template: str,
        indent: int = 2,
    ) -> str:
        """
        Generate dashboard as JSON string.

        Args:
            template: Template name.
            indent: JSON indentation.

        Returns:
            JSON string.
        """

        dashboard = self.generate(template)
        return json.dumps(dashboard, indent=indent)

    def generate_all_json(
        self,
        indent: int = 2,
    ) -> Dict[str, str]:
        """
        Generate all dashboards as JSON strings.

        Args:
            indent: JSON indentation.

        Returns:
            Dict mapping template name to JSON string.
        """

        return {
            name: self.generate_json(name, indent)
            for name in list_templates()
        }

    def generate_folder_config(
        self,
    ) -> Dict[str, Any]:
        """
        Generate Grafana folder configuration.

        Returns:
            Folder configuration dict.
        """

        return {
            "title": self._folder,
            "uid": self._uid_prefix,
        }

    def generate_datasource_config(
        self,
        url: str = "http://prometheus:9090",
    ) -> Dict[str, Any]:
        """
        Generate Grafana datasource configuration.

        Args:
            url: Prometheus URL.

        Returns:
            Datasource configuration dict.
        """

        return {
            "name": self._datasource,
            "type": "prometheus",
            "access": "proxy",
            "url": url,
            "isDefault": True,
            "editable": True,
        }

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get generator status.

        Returns:
            Status dictionary.
        """

        return {
            "datasource": self._datasource,
            "folder": self._folder,
            "uid_prefix": self._uid_prefix,
            "available_templates": list_templates(),
            "total_templates": len(DASHBOARD_TEMPLATES),
        }
