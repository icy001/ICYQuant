"""
ICYQuant Cloud Native Runtime - Cluster Manager

Manages multiple Kubernetes clusters with support for:
- Multi-cluster discovery
- Cluster health monitoring
- Resource utilization tracking
- Workload distribution
- Cross-cluster service discovery
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging
import uuid

logger = logging.getLogger(__name__)


class ClusterStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DEGRADED = "DEGRADED"
    MAINTENANCE = "MAINTENANCE"
    DRAINING = "DRAINING"


class ClusterRole(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    DR = "disaster-recovery"
    EDGE = "edge"


@dataclass
class ClusterResource:
    cpu_total: int = 0
    cpu_used: int = 0
    memory_total_gb: int = 0
    memory_used_gb: int = 0
    gpu_total: int = 0
    gpu_used: int = 0
    pods_total: int = 0
    pods_used: int = 0
    nodes: int = 0

    def to_dict(self) -> Dict:
        return {
            "cpuTotal": self.cpu_total,
            "cpuUsed": self.cpu_used,
            "cpuUtilization": self.cpu_used / max(self.cpu_total, 1) * 100,
            "memoryTotalGb": self.memory_total_gb,
            "memoryUsedGb": self.memory_used_gb,
            "memoryUtilization": self.memory_used_gb / max(self.memory_total_gb, 1) * 100,
            "gpuTotal": self.gpu_total,
            "gpuUsed": self.gpu_used,
            "podsTotal": self.pods_total,
            "podsUsed": self.pods_used,
            "nodes": self.nodes,
        }


@dataclass
class ClusterInfo:
    id: str
    name: str
    role: ClusterRole
    region: str
    status: ClusterStatus
    endpoint: str
    resources: ClusterResource = field(default_factory=ClusterResource)
    labels: Dict[str, str] = field(default_factory=dict)
    registered_at: datetime = field(default_factory=datetime.now)
    last_checked: Optional[datetime] = None

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "region": self.region,
            "status": self.status.value,
            "endpoint": self.endpoint,
            "resources": self.resources.to_dict(),
            "labels": self.labels,
        }


@dataclass
class WorkloadDistribution:
    service: str
    clusters: Dict[str, int] = field(default_factory=dict)
    total_replicas: int = 0

    def to_dict(self) -> Dict:
        return {
            "service": self.service,
            "clusters": self.clusters,
            "totalReplicas": self.total_replicas,
        }


class ClusterManager:
    """
    Multi-cluster management for ICYQuant platform.

    Provides:
    - Cluster registration and discovery
    - Cross-cluster health monitoring
    - Resource tracking and optimization
    - Workload distribution
    - Role-based cluster management
    """

    def __init__(self):
        self._clusters: Dict[str, ClusterInfo] = {}
        self._workloads: Dict[str, WorkloadDistribution] = {}
        self._health_checks: Dict[str, List[Dict]] = {}

    def register_cluster(
        self,
        name: str,
        role: ClusterRole,
        region: str,
        endpoint: str,
        resources: Optional[ClusterResource] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> ClusterInfo:
        cluster_id = str(uuid.uuid4())[:12]
        cluster = ClusterInfo(
            id=cluster_id,
            name=name,
            role=role,
            region=region,
            status=ClusterStatus.ACTIVE,
            endpoint=endpoint,
            resources=resources or ClusterResource(),
            labels=labels or {},
        )
        self._clusters[cluster_id] = cluster
        return cluster

    def update_cluster(
        self,
        cluster_id: str,
        status: Optional[ClusterStatus] = None,
        resources: Optional[ClusterResource] = None,
    ) -> Optional[ClusterInfo]:
        cluster = self._clusters.get(cluster_id)
        if not cluster:
            return None
        if status:
            cluster.status = status
        if resources:
            cluster.resources = resources
        cluster.last_checked = datetime.now()
        return cluster

    def remove_cluster(self, cluster_id: str) -> bool:
        if cluster_id in self._clusters:
            del self._clusters[cluster_id]
            return True
        return False

    def get_cluster(self, cluster_id: str) -> Optional[ClusterInfo]:
        return self._clusters.get(cluster_id)

    def list_clusters(
        self,
        role: Optional[ClusterRole] = None,
        status: Optional[ClusterStatus] = None,
    ) -> List[ClusterInfo]:
        results = list(self._clusters.values())
        if role:
            results = [c for c in results if c.role == role]
        if status:
            results = [c for c in results if c.status == status]
        return results

    def distribute_workload(
        self,
        service: str,
        total_replicas: int,
        cluster_ids: Optional[List[str]] = None,
    ) -> WorkloadDistribution:
        target_clusters = cluster_ids or list(self._clusters.keys())

        active_clusters = [
            c for c in self._clusters.values()
            if c.status == ClusterStatus.ACTIVE and c.id in target_clusters
        ]

        if not active_clusters:
            distribution = WorkloadDistribution(service=service)
            self._workloads[service] = distribution
            return distribution

        total_resource_score = sum(
            c.resources.cpu_total for c in active_clusters
        )
        if total_resource_score == 0:
            per_cluster = total_replicas // len(active_clusters)
            remainder = total_replicas % len(active_clusters)
            distributions = {}
            for i, cluster in enumerate(active_clusters):
                distributions[cluster.id] = per_cluster + (1 if i < remainder else 0)
        else:
            distributions = {}
            remaining = total_replicas
            for cluster in active_clusters:
                share = int(total_replicas * cluster.resources.cpu_total / total_resource_score)
                distributions[cluster.id] = share
                remaining -= share
            if remaining > 0:
                sorted_clusters = sorted(active_clusters, key=lambda c: c.resources.cpu_total, reverse=True)
                for i in range(remaining):
                    distributions[sorted_clusters[i % len(sorted_clusters)].id] += 1

        distribution = WorkloadDistribution(
            service=service,
            clusters=distributions,
            total_replicas=total_replicas,
        )
        self._workloads[service] = distribution
        return distribution

    def get_workload(self, service: str) -> Optional[WorkloadDistribution]:
        return self._workloads.get(service)

    def get_resource_summary(self) -> Dict:
        summary = {
            "total_cpu": 0,
            "used_cpu": 0,
            "total_memory_gb": 0,
            "used_memory_gb": 0,
            "total_gpu": 0,
            "used_gpu": 0,
            "clusters": [],
        }
        for cluster in self._clusters.values():
            r = cluster.resources
            summary["total_cpu"] += r.cpu_total
            summary["used_cpu"] += r.cpu_used
            summary["total_memory_gb"] += r.memory_total_gb
            summary["used_memory_gb"] += r.memory_used_gb
            summary["total_gpu"] += r.gpu_total
            summary["used_gpu"] += r.gpu_used
            summary["clusters"].append(cluster.to_dict())

        summary["cpu_utilization"] = (
            summary["used_cpu"] / max(summary["total_cpu"], 1) * 100
        )
        summary["memory_utilization"] = (
            summary["used_memory_gb"] / max(summary["total_memory_gb"], 1) * 100
        )
        return summary

    def get_status(self) -> Dict:
        return {
            "clusters": {c.id: c.to_dict() for c in self._clusters.values()},
            "workloads": {s: w.to_dict() for s, w in self._workloads.items()},
            "totalClusters": len(self._clusters),
            "activeClusters": sum(
                1 for c in self._clusters.values()
                if c.status == ClusterStatus.ACTIVE
            ),
        }