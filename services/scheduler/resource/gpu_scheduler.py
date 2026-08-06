"""GPU Scheduler — GPU-aware resource scheduling for AI/ML workloads.

The :class:`GPUScheduler` manages GPU resource allocation, considering
GPU model, memory, CUDA capability, and multi-GPU configurations.
Pre-allocates for AI inference and training scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GPUDevice:
    """A single GPU device."""

    device_id: str
    model: str = ""
    memory_mb: float = 0.0
    cuda_version: str = ""
    compute_capability: str = ""
    node_id: str = ""
    allocated: bool = False
    job_id: str = ""
    labels: Dict[str, str] = field(default_factory=dict)


class GPUScheduler:
    """GPU-aware scheduler for AI/ML workloads.

    Usage::

        gpu = GPUScheduler()
        gpu.register_device(GPUDevice("gpu-0", model="A100", memory_mb=81920, node_id="n1"))
        device = gpu.allocate(min_memory_mb=40960, preferred_model="A100")
    """

    def __init__(self) -> None:
        self._devices: Dict[str, GPUDevice] = {}

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------

    def register_device(self, device: GPUDevice) -> None:
        self._devices[device.device_id] = device

    def unregister_device(self, device_id: str) -> bool:
        return self._devices.pop(device_id, None) is not None

    # ------------------------------------------------------------------
    # Allocation
    # ------------------------------------------------------------------

    def allocate(
        self, job_id: str = "", min_memory_mb: float = 0.0,
        preferred_model: str = "", count: int = 1,
        node_id: Optional[str] = None,
    ) -> List[GPUDevice]:
        """Allocate one or more GPU devices matching criteria."""
        candidates = [
            d for d in self._devices.values()
            if not d.allocated
            and d.memory_mb >= min_memory_mb
            and (not preferred_model or d.model == preferred_model)
            and (node_id is None or d.node_id == node_id)
        ]

        # Sort: larger memory first, then by model preference
        candidates.sort(key=lambda d: (d.model == preferred_model, d.memory_mb), reverse=True)

        allocated = []
        for device in candidates[:count]:
            device.allocated = True
            device.job_id = job_id
            allocated.append(device)

        return allocated

    def release(self, device_id: str) -> bool:
        """Release a GPU device."""
        device = self._devices.get(device_id)
        if device is None:
            return False
        device.allocated = False
        device.job_id = ""
        return True

    def release_by_job(self, job_id: str) -> int:
        count = 0
        for device in self._devices.values():
            if device.job_id == job_id:
                device.allocated = False
                device.job_id = ""
                count += 1
        return count

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def available_count(self, min_memory_mb: float = 0.0, model: str = "") -> int:
        return sum(
            1 for d in self._devices.values()
            if not d.allocated
            and d.memory_mb >= min_memory_mb
            and (not model or d.model == model)
        )

    def total_count(self) -> int:
        return len(self._devices)

    def allocated_count(self) -> int:
        return sum(1 for d in self._devices.values() if d.allocated)

    def list_devices(self) -> List[GPUDevice]:
        return list(self._devices.values())

    def find_by_model(self, model: str) -> List[GPUDevice]:
        return [d for d in self._devices.values() if d.model == model]

    def utilization(self) -> Dict[str, Any]:
        total = len(self._devices)
        used = self.allocated_count()
        return {
            "total": total, "used": used, "free": total - used,
            "utilization_pct": used / max(total, 1) * 100,
        }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "devices_total": self.total_count(),
            "devices_used": self.allocated_count(),
            "devices_free": self.available_count(),
            "models": list({d.model for d in self._devices.values()}),
        }
