"""
Dashboard provisioning.

Manages automatic provisioning of Grafana
dashboards, folders, datasources, and
alert rules through configuration files
and API interactions.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from ..dashboard_models import DashboardTemplate
from .grafana import GrafanaDashboard
from .templates import (
    DASHBOARD_TEMPLATES,
    all_templates,
    list_templates,
)


class DashboardProvisioner:
    """
    Grafana dashboard provisioner.

    Generates Grafana provisioning configuration
    files and dashboard JSON for automated
    deployment to Grafana instances.

    Supports:
    - Dashboard JSON generation
    - Folder provisioning
    - Datasource provisioning
    - Alert rule provisioning

    Usage:
        provisioner = DashboardProvisioner(
            output_dir="/etc/grafana/provisioning",
        )
        provisioner.provision_all()
    """

    def __init__(
        self,
        generator: Optional[GrafanaDashboard] = None,
        output_dir: str = ".",
        prometheus_url: str = "http://prometheus:9090",
    ) -> None:
        """
        Initialize dashboard provisioner.

        Args:
            generator: Grafana dashboard generator.
            output_dir: Output directory for provisioning files.
            prometheus_url: Prometheus datasource URL.
        """

        self._generator = generator or GrafanaDashboard()
        self._output_dir = output_dir
        self._prometheus_url = prometheus_url
        self._provisioned: List[str] = []

    @property
    def generator(
        self,
    ) -> GrafanaDashboard:
        """Get dashboard generator."""
        return self._generator

    @property
    def provisioned(
        self,
    ) -> List[str]:
        """Get list of provisioned dashboards."""
        return self._provisioned

    def provision_dashboard(
        self,
        template_name: str,
    ) -> Dict[str, Any]:
        """
        Provision a single dashboard.

        Args:
            template_name: Template name.

        Returns:
            Provisioned dashboard dict.
        """

        dashboard = self._generator.generate(
            template_name
        )
        self._provisioned.append(template_name)
        return dashboard

    def provision_all(
        self,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Provision all dashboards.

        Returns:
            Dict mapping template name to dashboard dict.
        """

        return self._generator.generate_all()

    def provision_folders(
        self,
    ) -> Dict[str, Any]:
        """
        Provision Grafana folder configuration.

        Returns:
            Folder configuration dict.
        """

        return self._generator.generate_folder_config()

    def provision_datasource(
        self,
    ) -> Dict[str, Any]:
        """
        Provision Grafana datasource configuration.

        Returns:
            Datasource configuration dict.
        """

        return self._generator.generate_datasource_config(
            url=self._prometheus_url
        )

    def provision_alert_rules(
        self,
        rules: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Provision Grafana alert rules.

        Args:
            rules: Alert rule definitions. If None,
                   returns default infrastructure alert rules.

        Returns:
            List of alert rule dicts.
        """

        if rules is None:
            return self._default_alert_rules()

        return rules

    def _default_alert_rules(
        self,
    ) -> List[Dict[str, Any]]:
        """
        Generate default alert rules.

        Returns:
            List of alert rule configurations.
        """

        return [
            {
                "name": "High CPU Usage",
                "query": "icyquant_cpu_usage_percent > 90",
                "for_duration": "5m",
                "severity": "critical",
                "message": "CPU usage above 90% for 5 minutes",
            },
            {
                "name": "High Memory Usage",
                "query": "icyquant_memory_usage_percent > 85",
                "for_duration": "5m",
                "severity": "warning",
                "message": "Memory usage above 85% for 5 minutes",
            },
            {
                "name": "Disk Space Low",
                "query": "icyquant_disk_usage_percent > 90",
                "for_duration": "10m",
                "severity": "critical",
                "message": "Disk usage above 90%",
            },
            {
                "name": "Database Pool Exhausted",
                "query": "icyquant_database_active_connections / icyquant_database_pool_size > 0.9",
                "for_duration": "2m",
                "severity": "critical",
                "message": "Database connection pool near exhaustion",
            },
            {
                "name": "Redis Cache Hit Rate Low",
                "query": "icyquant_redis_cache_hit_ratio < 0.8",
                "for_duration": "10m",
                "severity": "warning",
                "message": "Redis cache hit rate below 80%",
            },
            {
                "name": "Kafka Consumer Lag",
                "query": "icyquant_kafka_consumer_failed_total > 0",
                "for_duration": "5m",
                "severity": "error",
                "message": "Kafka consumer errors detected",
            },
            {
                "name": "API Error Rate High",
                "query": "rate(icyquant_application_errors_total[5m]) > 0.1",
                "for_duration": "5m",
                "severity": "error",
                "message": "API error rate above threshold",
            },
        ]

    def generate_provisioning_config(
        self,
    ) -> Dict[str, Any]:
        """
        Generate complete provisioning configuration.

        Returns:
            Complete provisioning configuration dict.
        """

        return {
            "datasource": self.provision_datasource(),
            "folder": self.provision_folders(),
            "dashboards": self.provision_all(),
            "alert_rules": self.provision_alert_rules(),
        }

    def save_to_directory(
        self,
        directory: Optional[str] = None,
    ) -> List[str]:
        """
        Save provisioning files to directory.

        Args:
            directory: Target directory. Defaults to output_dir.

        Returns:
            List of saved file paths.
        """

        target = directory or self._output_dir
        saved_files: List[str] = []

        dashboards_dir = os.path.join(
            target, "dashboards"
        )
        os.makedirs(dashboards_dir, exist_ok=True)

        # Save each dashboard
        all_dashes = self.provision_all()
        for name, dashboard in all_dashes.items():
            filepath = os.path.join(
                dashboards_dir, f"{name}.json"
            )
            with open(filepath, "w") as f:
                json.dump(dashboard, f, indent=2)
            saved_files.append(filepath)

        # Save datasource config
        ds_config = self.provision_datasource()
        ds_path = os.path.join(
            target, "datasource.yaml"
        )
        with open(ds_path, "w") as f:
            f.write(
                "apiVersion: 1\n"
                "datasources:\n"
                f"  - {json.dumps(ds_config, indent=2)}\n"
            )
        saved_files.append(ds_path)

        # Save alert rules
        alerts = self.provision_alert_rules()
        alert_path = os.path.join(
            target, "alert_rules.json"
        )
        with open(alert_path, "w") as f:
            json.dump(alerts, f, indent=2)
        saved_files.append(alert_path)

        return saved_files

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get provisioner status.

        Returns:
            Status dictionary.
        """

        return {
            "output_dir": self._output_dir,
            "prometheus_url": self._prometheus_url,
            "provisioned": self._provisioned,
            "provisioned_count": len(self._provisioned),
            "generator": self._generator.get_status(),
        }
