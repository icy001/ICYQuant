from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class GPUStats:
    gpu_id: int
    name: str
    utilization_pct: float
    memory_used_mb: float
    memory_total_mb: float
    memory_used_pct: float
    temperature_c: float
    power_draw_w: float
    power_limit_w: float
    oom_events: int = 0
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def memory_free_pct(self) -> float:
        return 100.0 - self.memory_used_pct

    @property
    def is_healthy(self) -> bool:
        return (
            self.memory_used_pct < 95.0
            and self.temperature_c < 85.0
            and self.oom_events == 0
        )

    def to_dict(self) -> Dict:
        return {
            "gpu_id": self.gpu_id,
            "name": self.name,
            "utilization_pct": self.utilization_pct,
            "memory_used_mb": self.memory_used_mb,
            "memory_total_mb": self.memory_total_mb,
            "memory_used_pct": round(self.memory_used_pct, 1),
            "temperature_c": self.temperature_c,
            "power_draw_w": self.power_draw_w,
            "oom_events": self.oom_events,
            "healthy": self.is_healthy,
        }


@dataclass
class GPUClusterStatus:
    gpus: List[GPUStats] = field(default_factory=list)
    total_gpus: int = 0
    healthy_gpus: int = 0
    avg_utilization: float = 0.0
    avg_memory_used_pct: float = 0.0
    status: str = "UNKNOWN"
    checked_at: datetime = field(default_factory=datetime.now)


class GPUMonitor:
    def __init__(self):
        self._gpus: Dict[int, GPUStats] = {}
        self._history: List[GPUClusterStatus] = []
        self._memory_threshold = 95.0
        self._temp_threshold = 85.0

    def register_gpu(
        self,
        gpu_id: int,
        name: str = "GPU",
        memory_total_mb: float = 24576.0,
    ):
        self._gpus[gpu_id] = GPUStats(
            gpu_id=gpu_id,
            name=name,
            utilization_pct=0.0,
            memory_used_mb=0.0,
            memory_total_mb=memory_total_mb,
            memory_used_pct=0.0,
            temperature_c=45.0,
            power_draw_w=0.0,
            power_limit_w=300.0,
        )

    def update_stats(
        self,
        gpu_id: int,
        utilization_pct: float,
        memory_used_mb: float,
        temperature_c: float = 45.0,
        power_draw_w: float = 0.0,
        oom_events: int = 0,
    ) -> GPUStats:
        gpu = self._gpus.get(gpu_id)
        if not gpu:
            gpu = GPUStats(
                gpu_id=gpu_id,
                name=f"GPU_{gpu_id}",
                utilization_pct=utilization_pct,
                memory_used_mb=memory_used_mb,
                memory_total_mb=24576.0,
                memory_used_pct=(memory_used_mb / 24576.0) * 100,
                temperature_c=temperature_c,
                power_draw_w=power_draw_w,
                power_limit_w=300.0,
            )
            self._gpus[gpu_id] = gpu
        else:
            gpu.utilization_pct = utilization_pct
            gpu.memory_used_mb = memory_used_mb
            gpu.memory_used_pct = (memory_used_mb / gpu.memory_total_mb) * 100
            gpu.temperature_c = temperature_c
            gpu.power_draw_w = power_draw_w
            gpu.oom_events = oom_events
            gpu.last_updated = datetime.now()
        return gpu

    def get_gpu(self, gpu_id: int) -> Optional[GPUStats]:
        return self._gpus.get(gpu_id)

    def get_all_gpus(self) -> List[GPUStats]:
        return list(self._gpus.values())

    def get_cluster_status(self) -> GPUClusterStatus:
        gpus = list(self._gpus.values())
        total = len(gpus)
        healthy = sum(1 for g in gpus if g.is_healthy)
        avg_util = sum(g.utilization_pct for g in gpus) / total if total > 0 else 0
        avg_mem = sum(g.memory_used_pct for g in gpus) / total if total > 0 else 0

        if total == 0:
            status = "NO_GPUS"
        elif healthy == 0:
            status = "CRITICAL"
        elif healthy < total:
            status = "DEGRADED"
        else:
            status = "HEALTHY"

        cluster_status = GPUClusterStatus(
            gpus=gpus,
            total_gpus=total,
            healthy_gpus=healthy,
            avg_utilization=round(avg_util, 1),
            avg_memory_used_pct=round(avg_mem, 1),
            status=status,
        )
        self._history.append(cluster_status)
        return cluster_status

    def get_overloaded_gpus(self, memory_threshold: float = None) -> List[GPUStats]:
        threshold = memory_threshold or self._memory_threshold
        return [g for g in self._gpus.values() if g.memory_used_pct >= threshold]

    def get_available_memory(self, gpu_id: int) -> float:
        gpu = self._gpus.get(gpu_id)
        if gpu:
            return gpu.memory_total_mb - gpu.memory_used_mb
        return 0.0

    def get_best_available_gpu(self, required_memory_mb: float = 0) -> Optional[GPUStats]:
        candidates = [
            g for g in self._gpus.values()
            if (g.memory_total_mb - g.memory_used_mb) >= required_memory_mb
            and g.is_healthy
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda g: g.memory_used_pct)

    def set_thresholds(self, memory_threshold: float = None, temp_threshold: float = None):
        if memory_threshold is not None:
            self._memory_threshold = memory_threshold
        if temp_threshold is not None:
            self._temp_threshold = temp_threshold

    def get_cluster_status_dict(self) -> Dict:
        status = self.get_cluster_status()
        return {
            "total_gpus": status.total_gpus,
            "healthy_gpus": status.healthy_gpus,
            "avg_utilization": status.avg_utilization,
            "avg_memory_used_pct": status.avg_memory_used_pct,
            "status": status.status,
            "gpus": [g.to_dict() for g in status.gpus],
            "checked_at": status.checked_at.isoformat(),
        }
