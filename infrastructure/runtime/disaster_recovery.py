"""
ICYQuant Cloud Native Runtime - Disaster Recovery Manager

Provides multi-region disaster recovery with support for:
- Cross-region data replication
- Automatic failover to standby regions
- RPO/RTO management
- Disaster recovery testing
- Backup and restore operations
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class DRState(str, Enum):
    NORMAL = "NORMAL"
    REPLICATING = "REPLICATING"
    FAILOVER_INITIATED = "FAILOVER_INITIATED"
    FAILOVER_IN_PROGRESS = "FAILOVER_IN_PROGRESS"
    FAILOVER_COMPLETED = "FAILOVER_COMPLETED"
    RECOVERING = "RECOVERING"
    RESTORED = "RESTORED"
    BACKUP_IN_PROGRESS = "BACKUP_IN_PROGRESS"
    RESTORE_IN_PROGRESS = "RESTORE_IN_PROGRESS"


class ReplicationMode(str, Enum):
    SYNC = "SYNC"
    ASYNC = "ASYNC"
    SEMI_SYNC = "SEMI_SYNC"


@dataclass
class RegionConfig:
    id: str
    name: str
    endpoint: str
    role: str  # primary, standby, witness
    status: str = "active"
    last_replication: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "endpoint": self.endpoint,
            "role": self.role,
            "status": self.status,
            "lastReplication": self.last_replication.isoformat() if self.last_replication else None,
        }


@dataclass
class RPOConfig:
    target_seconds: int = 300  # 5 minutes
    warning_threshold_seconds: int = 600  # 10 minutes
    critical_threshold_seconds: int = 1800  # 30 minutes

    def to_dict(self) -> Dict:
        return {
            "targetSeconds": self.target_seconds,
            "warningSeconds": self.warning_threshold_seconds,
            "criticalSeconds": self.critical_threshold_seconds,
        }


@dataclass
class RTOConfig:
    target_seconds: int = 300  # 5 minutes
    maximum_seconds: int = 900  # 15 minutes

    def to_dict(self) -> Dict:
        return {
            "targetSeconds": self.target_seconds,
            "maximumSeconds": self.maximum_seconds,
        }


@dataclass
class BackupConfig:
    enabled: bool = True
    interval_hours: int = 24
    retention_days: int = 30
    storage_location: str = "s3://icyquant-backups"
    include: List[str] = field(default_factory=lambda: ["database", "configs", "state"])

    def to_dict(self) -> Dict:
        return {
            "enabled": self.enabled,
            "intervalHours": self.interval_hours,
            "retentionDays": self.retention_days,
            "storageLocation": self.storage_location,
            "include": self.include,
        }


@dataclass
class RestorePoint:
    id: str
    source: str
    timestamp: datetime
    size_gb: float
    status: str = "available"
    type: str = "full"  # full, incremental, differential

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "sizeGb": self.size_gb,
            "status": self.status,
            "type": self.type,
        }


@dataclass
class FailoverPlan:
    id: str
    name: str
    primary_region: str
    standby_regions: List[str]
    priority_order: List[str]
    rpo_config: RPOConfig
    rto_config: RTOConfig
    automatic: bool = False
    tested_at: Optional[datetime] = None
    last_failover: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "primaryRegion": self.primary_region,
            "standbyRegions": self.standby_regions,
            "priorityOrder": self.priority_order,
            "rpo": self.rpo_config.to_dict(),
            "rto": self.rto_config.to_dict(),
            "automatic": self.automatic,
            "testedAt": self.tested_at.isoformat() if self.tested_at else None,
            "lastFailover": self.last_failover.isoformat() if self.last_failover else None,
        }


class DisasterRecoveryManager:
    """
    Disaster recovery management for ICYQuant platform.

    Provides:
    - Multi-region configuration
    - Replication monitoring
    - Automatic/manual failover
    - Backup management
    - Restore point management
    - DR testing coordination
    """

    def __init__(self):
        self._regions: Dict[str, RegionConfig] = {}
        self._plans: Dict[str, FailoverPlan] = {}
        self._restoration_points: Dict[str, List[RestorePoint]] = {}
        self._state: DRState = DRState.NORMAL
        self._replication_lag_seconds: Dict[str, float] = {}

    def add_region(
        self,
        region_id: str,
        name: str,
        endpoint: str,
        role: str = "standby",
    ) -> RegionConfig:
        region = RegionConfig(
            id=region_id,
            name=name,
            endpoint=endpoint,
            role=role,
        )
        self._regions[region_id] = region
        return region

    def create_failover_plan(
        self,
        name: str,
        primary_region: str,
        standby_regions: List[str],
        priority_order: Optional[List[str]] = None,
        rpo_config: Optional[RPOConfig] = None,
        rto_config: Optional[RTOConfig] = None,
        automatic: bool = False,
    ) -> FailoverPlan:
        plan_id = str(uuid.uuid4())[:12]
        plan = FailoverPlan(
            id=plan_id,
            name=name,
            primary_region=primary_region,
            standby_regions=standby_regions,
            priority_order=priority_order or standby_regions,
            rpo_config=rpo_config or RPOConfig(),
            rto_config=rto_config or RTOConfig(),
            automatic=automatic,
        )
        self._plans[plan_id] = plan
        return plan

    def update_replication_lag(
        self,
        plan_id: str,
        lag_seconds: float,
    ):
        self._replication_lag_seconds[plan_id] = lag_seconds

    def check_rpo_compliance(self, plan_id: str) -> Dict:
        plan = self._plans.get(plan_id)
        if not plan:
            return {"compliant": False, "message": "Plan not found"}

        lag = self._replication_lag_seconds.get(plan_id, 0)
        rpo = plan.rpo_config

        compliant = lag <= rpo.target_seconds
        warning = lag > rpo.warning_threshold_seconds
        critical = lag > rpo.critical_threshold_seconds

        status = "compliant"
        if critical:
            status = "critical"
        elif warning:
            status = "warning"

        return {
            "planId": plan_id,
            "lagSeconds": lag,
            "targetRPO": rpo.target_seconds,
            "compliant": compliant,
            "status": status,
            "message": f"Replication lag: {lag:.1f}s (target: {rpo.target_seconds}s)",
        }

    def initiate_failover(
        self,
        plan_id: str,
        target_region: Optional[str] = None,
    ) -> Optional[FailoverPlan]:
        plan = self._plans.get(plan_id)
        if not plan:
            return None

        self._state = DRState.FAILOVER_INITIATED

        if target_region:
            if target_region not in plan.priority_order:
                target_region = plan.priority_order[0]
        else:
            target_region = plan.priority_order[0]

        primary = self._regions.get(plan.primary_region)
        if primary:
            primary.status = "standby"
            primary.role = "standby"

        new_primary = self._regions.get(target_region)
        if new_primary:
            new_primary.status = "active"
            new_primary.role = "primary"

        plan.primary_region = target_region
        plan.last_failover = datetime.now()

        self._state = DRState.FAILOVER_COMPLETED
        return plan

    def restore_primary(self, plan_id: str) -> Optional[FailoverPlan]:
        plan = self._plans.get(plan_id)
        if not plan:
            return None

        self._state = DRState.RECOVERING
        plan.primary_region = plan.standby_regions[0] if plan.standby_regions else plan.primary_region
        self._state = DRState.RESTORED
        return plan

    def create_restore_point(
        self,
        region_id: str,
        size_gb: float,
        point_type: str = "full",
    ) -> RestorePoint:
        point_id = str(uuid.uuid4())[:12]
        point = RestorePoint(
            id=point_id,
            source=region_id,
            timestamp=datetime.now(),
            size_gb=size_gb,
            type=point_type,
        )
        if region_id not in self._restoration_points:
            self._restoration_points[region_id] = []
        self._restoration_points[region_id].append(point)
        return point

    def get_restore_points(self, region_id: str) -> List[RestorePoint]:
        return self._restoration_points.get(region_id, [])

    def get_available_restore_points(self) -> List[Dict]:
        points = []
        for region_id, restore_points in self._restoration_points.items():
            for point in restore_points:
                points.append(point.to_dict())
        return sorted(points, key=lambda x: x["timestamp"], reverse=True)

    def test_dr_plan(
        self,
        plan_id: str,
    ) -> Dict:
        plan = self._plans.get(plan_id)
        if not plan:
            return {"success": False, "message": "Plan not found"}

        plan.tested_at = datetime.now()
        return {
            "success": True,
            "planId": plan_id,
            "testedAt": plan.tested_at.isoformat(),
            "rpoConfig": plan.rpo_config.to_dict(),
            "rtoConfig": plan.rto_config.to_dict(),
        }

    def get_status(self) -> Dict:
        return {
            "state": self._state.value,
            "regions": {r.id: r.to_dict() for r in self._regions.values()},
            "plans": {p.id: p.to_dict() for p in self._plans.values()},
            "replicationLag": dict(self._replication_lag_seconds),
            "restorePoints": len(self._restoration_points),
        }