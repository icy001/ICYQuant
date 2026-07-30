from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class GrafanaPanel:
    panel_id: str
    title: str
    panel_type: str
    grid_pos: Dict
    datasource: str
    targets: List[Dict] = field(default_factory=list)


@dataclass
class GrafanaDashboard:
    dashboard_id: str
    title: str
    panels: List[GrafanaPanel]
    tags: List[str] = field(default_factory=list)
    refresh_interval: str = "30s"
    time_range: Dict = field(default_factory=lambda: {"from": "now-1h", "to": "now"})


class GrafanaDashboardAdapter:
    def __init__(self, url: str = "http://localhost:3000"):
        self.url = url
        self._dashboards: Dict[str, GrafanaDashboard] = {}

    def create_dashboard(
        self,
        dashboard_id: str,
        title: str,
        panels: Optional[List[GrafanaPanel]] = None,
        tags: Optional[List[str]] = None,
    ) -> GrafanaDashboard:
        dashboard = GrafanaDashboard(
            dashboard_id=dashboard_id,
            title=title,
            panels=panels or [],
            tags=tags or [],
        )
        self._dashboards[dashboard_id] = dashboard
        return dashboard

    def add_panel(
        self,
        dashboard_id: str,
        panel_id: str,
        title: str,
        panel_type: str = "graph",
        datasource: str = "Prometheus",
    ):
        dashboard = self._dashboards.get(dashboard_id)
        if dashboard:
            panel = GrafanaPanel(
                panel_id=panel_id,
                title=title,
                panel_type=panel_type,
                grid_pos={"h": 8, "w": 12, "x": 0, "y": 0},
                datasource=datasource,
            )
            dashboard.panels.append(panel)

    def get_dashboard(self, dashboard_id: str) -> Optional[GrafanaDashboard]:
        return self._dashboards.get(dashboard_id)

    def list_dashboards(self) -> List[GrafanaDashboard]:
        return list(self._dashboards.values())

    def get_dashboard_json(self, dashboard_id: str) -> Dict:
        dashboard = self._dashboards.get(dashboard_id)
        if not dashboard:
            return {}
        return {
            "id": dashboard.dashboard_id,
            "title": dashboard.title,
            "tags": dashboard.tags,
            "refresh": dashboard.refresh_interval,
            "time": dashboard.time_range,
            "panels": [
                {
                    "id": idx + 1,
                    "title": p.title,
                    "type": p.panel_type,
                    "datasource": p.datasource,
                    "gridPos": p.grid_pos,
                }
                for idx, p in enumerate(dashboard.panels)
            ],
        }

    def get_default_dashboard(self) -> Dict:
        return self.get_dashboard_json("system_overview")

    def clear(self):
        self._dashboards.clear()
