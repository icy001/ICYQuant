"""
Throughput benchmark for measuring system throughput.

Measures TPS (Transactions Per Second), orders per second, messages per second,
and concurrent connection handling with ramp-up testing support.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ThroughputResult:
    name: str
    duration: float
    total_requests: int
    successful: int
    failed: int
    tps: float
    peak_tps: float
    avg_latency: float
    min_latency: float
    max_latency: float
    error_rate: float
    concurrency_levels: list[int] = field(default_factory=list)
    throughput_per_level: dict[int, float] = field(default_factory=dict)


class ThroughputBenchmark:
    """
    Measures system throughput under various concurrency levels.

    Supports ramp-up testing with configurable duration and concurrency,
    tracking success/failure rates and latency statistics.
    """

    def __init__(
        self,
        duration: float = 10.0,
        concurrency_levels: Optional[list[int]] = None,
        ramp_up_delay: float = 1.0,
    ):
        self.duration = duration
        self.concurrency_levels = concurrency_levels or [10, 50, 100, 500]
        self.ramp_up_delay = ramp_up_delay

    def measure_tps(
        self,
        func: Callable[[], None],
        name: str = "tps_benchmark",
    ) -> ThroughputResult:
        return self._run_throughput_test(func, name, self.concurrency_levels)

    def measure_orders_per_second(
        self,
        order_func: Callable[[], None],
    ) -> ThroughputResult:
        return self._run_throughput_test(
            order_func, "orders_per_second", self.concurrency_levels
        )

    def measure_messages_per_second(
        self,
        message_func: Callable[[], None],
    ) -> ThroughputResult:
        return self._run_throughput_test(
            message_func, "messages_per_second", self.concurrency_levels
        )

    def measure_concurrent_connections(
        self,
        connection_func: Callable[[], None],
        max_concurrency: int = 1000,
    ) -> ThroughputResult:
        levels = [level for level in self.concurrency_levels if level <= max_concurrency]
        if max_concurrency not in levels:
            levels.append(max_concurrency)
        return self._run_throughput_test(connection_func, "concurrent_connections", levels)

    def _run_throughput_test(
        self,
        func: Callable[[], None],
        name: str,
        concurrency_levels: list[int],
    ) -> ThroughputResult:
        all_latencies: list[float] = []
        total_successful = 0
        total_failed = 0
        peak_tps = 0.0
        throughput_per_level: dict[int, float] = {}

        for level in concurrency_levels:
            latencies: list[float] = []
            successful = 0
            failed = 0
            lock = threading.Lock()
            stop_event = threading.Event()

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
                    except Exception:
                        with lock:
                            failed += 1

            threads = [threading.Thread(target=worker) for _ in range(level)]
            for t in threads:
                t.daemon = True
                t.start()

            time.sleep(self.duration)
            stop_event.set()

            for t in threads:
                t.join(timeout=2.0)

            level_duration = self.duration
            level_tps = successful / level_duration if level_duration > 0 else 0.0
            throughput_per_level[level] = level_tps
            peak_tps = max(peak_tps, level_tps)

            total_successful += successful
            total_failed += failed
            all_latencies.extend(latencies)

            time.sleep(self.ramp_up_delay)

        total_requests = total_successful + total_failed
        overall_duration = self.duration * len(concurrency_levels)
        overall_tps = total_requests / overall_duration if overall_duration > 0 else 0.0
        error_rate = total_failed / total_requests if total_requests > 0 else 0.0

        avg_latency = sum(all_latencies) / len(all_latencies) if all_latencies else 0.0
        min_latency = min(all_latencies) if all_latencies else 0.0
        max_latency = max(all_latencies) if all_latencies else 0.0

        return ThroughputResult(
            name=name,
            duration=overall_duration,
            total_requests=total_requests,
            successful=total_successful,
            failed=total_failed,
            tps=overall_tps,
            peak_tps=peak_tps,
            avg_latency=avg_latency,
            min_latency=min_latency,
            max_latency=max_latency,
            error_rate=error_rate,
            concurrency_levels=concurrency_levels,
            throughput_per_level=throughput_per_level,
        )