"""
Latency benchmark for measuring API and operation latency.

Provides precise latency measurements using time.perf_counter() with
percentile calculations (P50, P95, P99) for comprehensive analysis.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class BenchmarkResult:
    name: str
    duration: float
    samples: int
    mean: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    min: float = 0.0
    max: float = 0.0
    std_dev: float = 0.0
    raw_samples: list[float] = field(default_factory=list)


class LatencyBenchmark:
    """
    Measures latency of various system operations with high precision.

    Supports API calls, order submissions, market data propagation,
    and AI inference latency measurements with percentile statistics.
    """

    def __init__(self, warmup: int = 10, iterations: int = 100):
        self.warmup = warmup
        self.iterations = iterations

    def measure(
        self,
        func: Callable[[], None],
        name: str = "benchmark",
        iterations: Optional[int] = None,
        warmup: Optional[int] = None,
    ) -> BenchmarkResult:
        iters = iterations or self.iterations
        warm = warmup if warmup is not None else self.warmup

        for _ in range(warm):
            func()

        samples: list[float] = []
        for _ in range(iters):
            start = time.perf_counter()
            func()
            elapsed = (time.perf_counter() - start) * 1000
            samples.append(elapsed)

        return self._build_result(name, samples)

    def measure_api(
        self,
        endpoint_func: Callable[[], None],
        endpoint_name: str = "api_call",
    ) -> BenchmarkResult:
        return self.measure(endpoint_func, f"api:{endpoint_name}")

    def measure_order(
        self,
        order_func: Callable[[], None],
        order_type: str = "order_submit",
    ) -> BenchmarkResult:
        return self.measure(order_func, f"order:{order_type}")

    def measure_market_data(
        self,
        data_func: Callable[[], None],
        data_type: str = "market_data",
    ) -> BenchmarkResult:
        return self.measure(data_func, f"market:{data_type}")

    def measure_ai_inference(
        self,
        inference_func: Callable[[], None],
        model_name: str = "ai_inference",
    ) -> BenchmarkResult:
        return self.measure(inference_func, f"ai:{model_name}")

    @staticmethod
    def _build_result(name: str, samples: list[float]) -> BenchmarkResult:
        sorted_samples = sorted(samples)
        n = len(sorted_samples)

        mean = statistics.mean(sorted_samples) if n > 0 else 0.0
        p50 = LatencyBenchmark._percentile(sorted_samples, 50)
        p95 = LatencyBenchmark._percentile(sorted_samples, 95)
        p99 = LatencyBenchmark._percentile(sorted_samples, 99)
        min_val = sorted_samples[0] if n > 0 else 0.0
        max_val = sorted_samples[-1] if n > 0 else 0.0
        std_dev = statistics.stdev(sorted_samples) if n > 1 else 0.0

        total_duration = sum(sorted_samples)

        return BenchmarkResult(
            name=name,
            duration=total_duration,
            samples=n,
            mean=mean,
            p50=p50,
            p95=p95,
            p99=p99,
            min=min_val,
            max=max_val,
            std_dev=std_dev,
            raw_samples=sorted_samples,
        )

    @staticmethod
    def _percentile(sorted_data: list[float], pct: float) -> float:
        if not sorted_data:
            return 0.0
        if len(sorted_data) == 1:
            return sorted_data[0]

        k = (pct / 100.0) * (len(sorted_data) - 1)
        f = int(k)
        c = f + 1
        if c >= len(sorted_data):
            return sorted_data[-1]
        d0 = sorted_data[f] * (c - k)
        d1 = sorted_data[c] * (k - f)
        return d0 + d1