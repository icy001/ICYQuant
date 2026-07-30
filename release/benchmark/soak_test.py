"""
Long-running stability testing module (soak testing).

Performs extended stability testing over configurable periods (24h, 72h, 7d)
and monitors memory leaks, handle/resource leaks, CPU drift, thread growth,
and performance degradation over time.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class SoakMetrics:
    timestamp: float
    cpu_percent: float = 0.0
    memory_bytes: int = 0
    thread_count: int = 0
    open_handles: int = 0
    operations_completed: int = 0
    operation_latency: float = 0.0


@dataclass
class SoakResult:
    name: str
    duration: float
    total_operations: int
    successful_operations: int
    failed_operations: int
    operations_per_hour: float
    avg_latency: float
    memory_leak_detected: bool = False
    memory_growth_bytes: int = 0
    handle_leak_detected: bool = False
    handle_growth: int = 0
    cpu_drift_detected: bool = False
    cpu_drift_percent: float = 0.0
    thread_growth_detected: bool = False
    thread_growth_count: int = 0
    performance_degradation: float = 0.0
    metrics_over_time: list[SoakMetrics] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class SoakTest:
    """
    Extended stability testing for detecting long-term issues.

    Monitors resource usage trends over extended periods to identify
    memory leaks, handle leaks, CPU drift, thread growth, and
    performance degradation.
    """

    def __init__(
        self,
        duration_hours: float = 24.0,
        monitor_interval: float = 60.0,
        operation_interval: float = 0.01,
        leak_detection_threshold: float = 0.1,
    ):
        self.duration_hours = duration_hours
        self.monitor_interval = monitor_interval
        self.operation_interval = operation_interval
        self.leak_detection_threshold = leak_detection_threshold

    def run(
        self,
        func: Callable[[], None],
        name: str = "soak_test",
    ) -> SoakResult:
        duration_seconds = self.duration_hours * 3600.0
        start_time = time.perf_counter()
        end_time = start_time + duration_seconds

        metrics_over_time: list[SoakMetrics] = []
        errors: list[str] = []
        successful = 0
        failed = 0
        total_latency = 0.0
        latency_count = 0

        stop_event = threading.Event()

        def operation_loop() -> None:
            nonlocal successful, failed, total_latency, latency_count
            while not stop_event.is_set():
                op_start = time.perf_counter()
                try:
                    func()
                    elapsed = (time.perf_counter() - op_start) * 1000
                    with threading.Lock():
                        successful += 1
                        total_latency += elapsed
                        latency_count += 1
                except Exception as e:
                    with threading.Lock():
                        failed += 1
                        errors.append(str(e))
                time.sleep(self.operation_interval)

        operation_thread = threading.Thread(target=operation_loop, daemon=True)
        operation_thread.start()

        last_monitor = start_time
        initial_metrics: Optional[SoakMetrics] = None
        peak_memory = 0
        peak_threads = 0

        while time.perf_counter() < end_time:
            now = time.perf_counter()
            if now - last_monitor >= self.monitor_interval:
                metrics = self._capture_metrics(successful, latency_count, total_latency)
                metrics_over_time.append(metrics)

                if initial_metrics is None:
                    initial_metrics = metrics

                peak_memory = max(peak_memory, metrics.memory_bytes)
                peak_threads = max(peak_threads, metrics.thread_count)

                last_monitor = now

            remaining = end_time - time.perf_counter()
            if remaining <= 0:
                break
            time.sleep(min(remaining, 1.0))

        stop_event.set()
        operation_thread.join(timeout=5.0)

        final_metrics = self._capture_metrics(successful, latency_count, total_latency)
        if initial_metrics is None:
            initial_metrics = final_metrics

        total_duration = time.perf_counter() - start_time
        total_ops = successful + failed
        ops_per_hour = total_ops / self.duration_hours if self.duration_hours > 0 else 0.0
        avg_latency = total_latency / latency_count if latency_count > 0 else 0.0

        memory_leak, memory_growth = self._detect_memory_leak(
            initial_metrics, final_metrics, peak_memory
        )
        handle_leak, handle_growth = self._detect_handle_leak(
            initial_metrics, final_metrics
        )
        cpu_drift, cpu_drift_pct = self._detect_cpu_drift(
            initial_metrics, final_metrics
        )
        thread_growth, thread_growth_count = self._detect_thread_growth(
            initial_metrics, final_metrics, peak_threads
        )
        perf_degradation = self._detect_performance_degradation(metrics_over_time)

        return SoakResult(
            name=name,
            duration=total_duration,
            total_operations=total_ops,
            successful_operations=successful,
            failed_operations=failed,
            operations_per_hour=ops_per_hour,
            avg_latency=avg_latency,
            memory_leak_detected=memory_leak,
            memory_growth_bytes=memory_growth,
            handle_leak_detected=handle_leak,
            handle_growth=handle_growth,
            cpu_drift_detected=cpu_drift,
            cpu_drift_percent=cpu_drift_pct,
            thread_growth_detected=thread_growth,
            thread_growth_count=thread_growth_count,
            performance_degradation=perf_degradation,
            metrics_over_time=metrics_over_time,
            errors=errors,
        )

    def _capture_metrics(
        self,
        operations: int,
        latency_count: int,
        total_latency: float,
    ) -> SoakMetrics:
        cpu = SoakTest._measure_cpu()
        mem = SoakTest._measure_memory()
        threads = threading.active_count()
        handles = SoakTest._count_handles()

        avg_lat = total_latency / latency_count if latency_count > 0 else 0.0

        return SoakMetrics(
            timestamp=time.time(),
            cpu_percent=cpu,
            memory_bytes=mem,
            thread_count=threads,
            open_handles=handles,
            operations_completed=operations,
            operation_latency=avg_lat,
        )

    def _detect_memory_leak(
        self,
        initial: SoakMetrics,
        final: SoakMetrics,
        peak: int,
    ) -> tuple[bool, int]:
        growth = final.memory_bytes - initial.memory_bytes
        if initial.memory_bytes > 0:
            growth_ratio = growth / initial.memory_bytes
            if growth_ratio > self.leak_detection_threshold:
                return True, growth
        return False, growth

    def _detect_handle_leak(
        self,
        initial: SoakMetrics,
        final: SoakMetrics,
    ) -> tuple[bool, int]:
        growth = final.open_handles - initial.open_handles
        if initial.open_handles > 0:
            growth_ratio = growth / initial.open_handles
            if growth_ratio > self.leak_detection_threshold:
                return True, growth
        return False, growth

    def _detect_cpu_drift(
        self,
        initial: SoakMetrics,
        final: SoakMetrics,
    ) -> tuple[bool, float]:
        drift = final.cpu_percent - initial.cpu_percent
        if initial.cpu_percent > 0:
            drift_ratio = drift / initial.cpu_percent
            if drift_ratio > self.leak_detection_threshold:
                return True, drift
        return False, drift

    def _detect_thread_growth(
        self,
        initial: SoakMetrics,
        final: SoakMetrics,
        peak: int,
    ) -> tuple[bool, int]:
        growth = final.thread_count - initial.thread_count
        if initial.thread_count > 0:
            growth_ratio = growth / initial.thread_count
            if growth_ratio > self.leak_detection_threshold:
                return True, growth
        return False, growth

    def _detect_performance_degradation(
        self,
        metrics: list[SoakMetrics],
    ) -> float:
        if len(metrics) < 2:
            return 0.0
        first = metrics[0]
        last = metrics[-1]
        if first.operation_latency > 0:
            return (last.operation_latency - first.operation_latency) / first.operation_latency
        return 0.0

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
    def _count_handles() -> int:
        try:
            import resource as res

            return res.getrusage(res.RUSAGE_SELF).ru_maxrss
        except ImportError:
            return 0