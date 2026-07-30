from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class DashboardPanel:
    panel_id: str
    title: str
    panel_type: str
    data: Dict
    refresh_interval: int = 30


@dataclass
class DashboardSnapshot:
    snapshot_id: str
    timestamp: datetime
    panels: List[DashboardPanel]
    system_health: str
    ai_health: str
    trading_health: str
    risk_health: str
    active_alerts: int
    active_incidents: int


class DashboardManager:
    def __init__(self):
        self._panels: Dict[str, DashboardPanel] = {}
        self._snapshots: List[DashboardSnapshot] = []

    def register_panel(
        self,
        panel_id: str,
        title: str,
        panel_type: str,
        data: Optional[Dict] = None,
        refresh_interval: int = 30,
    ) -> DashboardPanel:
        panel = DashboardPanel(
            panel_id=panel_id,
            title=title,
            panel_type=panel_type,
            data=data or {},
            refresh_interval=refresh_interval,
        )
        self._panels[panel_id] = panel
        return panel

    def update_panel(self, panel_id: str, data: Dict):
        if panel_id in self._panels:
            self._panels[panel_id].data = data

    def get_panel(self, panel_id: str) -> Optional[DashboardPanel]:
        return self._panels.get(panel_id)

    def list_panels(self) -> List[DashboardPanel]:
        return list(self._panels.values())

    def create_snapshot(
        self,
        system_health: str = "HEALTHY",
        ai_health: str = "HEALTHY",
        trading_health: str = "HEALTHY",
        risk_health: str = "HEALTHY",
        active_alerts: int = 0,
        active_incidents: int = 0,
    ) -> DashboardSnapshot:
        import uuid
        snapshot = DashboardSnapshot(
            snapshot_id=uuid.uuid4().hex[:12],
            timestamp=datetime.now(),
            panels=list(self._panels.values()),
            system_health=system_health,
            ai_health=ai_health,
            trading_health=trading_health,
            risk_health=risk_health,
            active_alerts=active_alerts,
            active_incidents=active_incidents,
        )
        self._snapshots.append(snapshot)
        return snapshot

    def get_latest_snapshot(self) -> Optional[DashboardSnapshot]:
        if self._snapshots:
            return self._snapshots[-1]
        return None

    def get_snapshot_history(self, limit: int = 20) -> List[DashboardSnapshot]:
        return sorted(self._snapshots, key=lambda s: s.timestamp, reverse=True)[:limit]

    def build_system_panel(self, system_status: Dict) -> DashboardPanel:
        return self.register_panel(
            panel_id="system",
            title="System Status",
            panel_type="STATUS",
            data=system_status,
        )

    def build_ai_panel(self, ai_status: Dict) -> DashboardPanel:
        return self.register_panel(
            panel_id="ai",
            title="AI Services",
            panel_type="AI_STATUS",
            data=ai_status,
        )

    def build_trading_panel(self, trading_status: Dict) -> DashboardPanel:
        return self.register_panel(
            panel_id="trading",
            title="Trading System",
            panel_type="TRADING_STATUS",
            data=trading_status,
        )

    def build_risk_panel(self, risk_status: Dict) -> DashboardPanel:
        return self.register_panel(
            panel_id="risk",
            title="Risk Engine",
            panel_type="RISK_STATUS",
            data=risk_status,
        )

    def build_gpu_panel(self, gpu_status: Dict) -> DashboardPanel:
        return self.register_panel(
            panel_id="gpu",
            title="GPU Cluster",
            panel_type="GPU_STATUS",
            data=gpu_status,
        )

    def build_alerts_panel(self, alerts: List[Dict]) -> DashboardPanel:
        return self.register_panel(
            panel_id="alerts",
            title="Active Alerts",
            panel_type="ALERTS",
            data={"alerts": alerts, "count": len(alerts)},
        )

    def clear(self):
        self._panels.clear()
        self._snapshots.clear()
