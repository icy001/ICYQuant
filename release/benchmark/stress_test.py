"""
Stress testing module for pushing system to its limits.

Monitors CPU, memory, and thread count during stress testing,
detects degradation thresholds, and reports maximum sustainable TPS.
Uses only Python standard library for portability.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ResourceMetrics:
    cpu_percent: float = 0.0
    memory_bytes: int = 0
    thread_count: int = 0
    open_handles: int = 0


@dataclass
class StressResult:
    name: str
    max_sustainable_tps: float
    peak_tps: float
    breaking_point_tps: float
    duration: float
    concurrency_levels_tested: list[int] = field(default_factory=list)
    resource_at_peak: ResourceMetrics = field(default_factory=ResourceMetrics)
    resource_at_break: ResourceMetrics = field(default_factory=ResourceMetrics)
    degradation_threshold: float = 0.1
    errors: list[str] = field(default_factory=list)


class StressTest:
    """
    Pushes the system to its limits by incrementally increasing load.

    Monitors resource usage and detects degradation thresholds to
    identify the maximum sustainable TPS before system failure.
    Uses Python standard library only for cross-platform compatibility.
    """

    def __init__(
        self,
        duration_per_level: float = 30.0,
        concurrency_levels: Optional[list[int]] = None,
        degradation_threshold: float = 0.1,
        monitor_interval: float = 1.0,
    ):
        self.duration_per_level = duration_per_level
        self.concurrency_levels = concurrency_levels or [100, 500, 1000, 5000]
        self.degradation_threshold = degradation_threshold
        self.monitor_interval = monitor_interval

    def run(
        self,
        func: Callable[[], None],
        name: str = "stress_test",
    ) -> StressResult:
        max_tps = 0.0
        peak_tps = 0.0
        breaking_point = 0.0
        errors: list[str] = []
        resource_at_peak = ResourceMetrics()
        resource_at_break = ResourceMetrics()

        prev_tps = None

        for level in self.concurrency_levels:
            result, err = self._run_single_level(func, level)
            if err:
                errors.append(err)

            current_tps = result["tps"]
            peak_tps = max(peak_tps, current_tps)
            resource_at_peak = result["resource"]

            if prev_tps is not None and prev_tps > 0:
                degradation = (prev_tps - current_tps) / prev_tps
                if degradation > self.degradation_threshold:
                    breaking_point = level
                    resource_at_break = result["resource"]
                    break

            if result["successful"] > 0:
                max_tps = current_tps

            prev_tps = current_tps

        return StressResult(
            name=name,
            max_sustainable_tps=max_tps,
            peak_tps=peak_tps,
            breaking_point_tps=float(breaking_point),
            duration=self.duration_per_level * len(self.concurrency_levels),
            concurrency_levels_tested=self.concurrency_levels,
            resource_at_peak=resource_at_peak,
            resource_at_break=resource_at_break,
            degradation_threshold=self.degradation_threshold,
            errors=errors,
        )

    def _run_single_level(
        self,
        func: Callable[[], None],
        concurrency: int,
    ) -> tuple[dict, Optional[str]]:
        latencies: list[float] = []
        successful = 0
        failed = 0
        lock = threading.Lock()
        stop_event = threading.Event()
        errors: list[str] = []

        def worker() -> None:
            nonlocal successful, failed
            while not stop_event.is_set():
                start = time.perf_counter()
                try:
                    func()
                    elapsed = (time.perf_counter() - start) * 1000
                    with lock:
                        latencies.append(elapsed)
                        successful += 1
                except Exception as e:
                    with lock:
                        failed += 1
                        errors.append(str(e))

        threads = [threading.Thread(target=worker) for _ in range(concurrency)]
        for t in threads:
            t.daemon = True
            t.start()

        time.sleep(self.duration_per_level)
        stop_event.set()

        for t in threads:
            t.join(timeout=5.0)

        total_time = self.duration_per_level
        tps = successful / total_time if total_time > 0 else 0.0
        error_rate = failed / (successful + failed) if (successful + failed) > 0 else 0.0

        resource = self._capture_resources(concurrency)

        result = {
            "tps": tps,
            "successful": successful,
            "failed": failed,
            "error_rate": error_rate,
            "resource": resource,
        }

        error_msg = None
        if error_rate > self.degradation_threshold:
            error_msg = f"High error rate at concurrency {concurrency}: {error_rate:.2%}"

        return result, error_msg

    @staticmethod
    def _capture_resources(concurrency: int) -> ResourceMetrics:
        cpu_percent = StressTest._measure_cpu()
        memory_bytes = StressTest._measure_memory()
        thread_count = threading.active_count()
        open_handles = StressTest._count_open_handles()

        return ResourceMetrics(
            cpu_percent=cpu_percent,
            memory_bytes=memory_bytes,
            thread_count=thread_count,
            open_handles=open_handles,
        )

    @staticmethod
    def _measure_cpu() -> float:
        try:
            proc_start = time.process_time()
            wall_start = time.perf_counter()
            time.sleep(0.1)
            proc_end = time.process_time()
            wall_end = time.perf_counter()

            proc_delta = proc_end - proc_start
            wall_delta = wall_end - wall_start
            if wall_delta > 0:
                return (proc_delta / wall_delta) * 100.0
            return 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _measure_memory() -> int:
        try:
            import resource as res

            return res.getrusage(res.RUSAGE_SELF).ru_maxrss * 1024
        except ImportError:
            return 0

    @staticmethod
    def _count_open_handles() -> int:
        try:
            import resource as res

            return res.getrusage(res.RUSAGE_SELF).ru_maxrss
        except ImportError:
            return 0