"""
Analytics Metrics — Prometheus-compatible metrics for the enterprise risk analytics platform.

Exposes counters, gauges, histograms, and summaries for monitoring
analytics operations, performance, and error rates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricsRegistry:
    """In-memory metrics registry (Prometheus-compatible structure)."""

    counters: dict[str, float] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
    histograms: dict[str, list[float]] = field(default_factory=dict)
    labels: dict[str, dict[str, str]] = field(default_factory=dict)


class AnalyticsMetrics:
    """
    Metrics collector for the enterprise risk analytics platform.

    Tracks:
    - VaR calculations (total, by method, errors)
    - CVaR calculations
    - Stress test runs (total, scenarios, failures)
    - Monte Carlo simulation (paths generated, convergence)
    - Risk report generation
    - Scenario runs
    - Capital ratio
    - Analysis pipeline latency
    - Subsystem error counts
    """

    def __init__(self) -> None:
        self._registry = MetricsRegistry()

    # ---- Counters ----

    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        full_name = f"icyquant_{name}"
        self._registry.counters[full_name] = self._registry.counters.get(full_name, 0) + value
        if labels:
            self._registry.labels[full_name] = labels

    def get_counter(self, name: str) -> float:
        """Get a counter value."""
        full_name = f"icyquant_{name}"
        return self._registry.counters.get(full_name, 0)

    # ---- Gauges ----

    def set_gauge(self, name: str, value: float, labels: Optional[dict[str, str]] = None) -> None:
        """Set a gauge metric."""
        full_name = f"icyquant_{name}"
        self._registry.gauges[full_name] = value
        if labels:
            self._registry.labels[full_name] = labels

    def get_gauge(self, name: str) -> float:
        """Get a gauge value."""
        full_name = f"icyquant_{name}"
        return self._registry.gauges.get(full_name, 0)

    # ---- Histograms ----

    def observe_histogram(self, name: str, value: float) -> None:
        """Record a histogram observation."""
        full_name = f"icyquant_{name}"
        if full_name not in self._registry.histograms:
            self._registry.histograms[full_name] = []
        self._registry.histograms[full_name].append(value)
        # Keep last 10000 observations
        if len(self._registry.histograms[full_name]) > 10000:
            self._registry.histograms[full_name] = self._registry.histograms[full_name][-10000:]

    def get_histogram_stats(self, name: str) -> dict[str, float]:
        """Get histogram statistics."""
        full_name = f"icyquant_{name}"
        values = self._registry.histograms.get(full_name, [])
        if not values:
            return {"count": 0, "sum": 0, "avg": 0, "min": 0, "max": 0}
        sorted_vals = sorted(values)
        return {
            "count": len(sorted_vals),
            "sum": sum(sorted_vals),
            "avg": sum(sorted_vals) / len(sorted_vals),
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "p50": sorted_vals[len(sorted_vals) // 2],
            "p95": sorted_vals[int(len(sorted_vals) * 0.95)],
            "p99": sorted_vals[int(len(sorted_vals) * 0.99)],
        }

    # ---- Domain-Specific Metrics ----

    def record_var_calculation(self, method: str, success: bool = True, elapsed_ms: float = 0) -> None:
        """Record a VaR calculation."""
        self.increment_counter("var_calculations_total")
        self.increment_counter(f"var_calculations_{method}")
        if not success:
            self.increment_counter("var_calculation_errors_total")
        self.observe_histogram("var_calculation_duration_ms", elapsed_ms)

    def record_cvar_calculation(self, success: bool = True, elapsed_ms: float = 0) -> None:
        """Record a CVaR calculation."""
        self.increment_counter("cvar_calculations_total")
        if not success:
            self.increment_counter("cvar_calculation_errors_total")
        self.observe_histogram("cvar_calculation_duration_ms", elapsed_ms)

    def record_stress_test(self, scenarios: int = 0, failed: int = 0, elapsed_ms: float = 0) -> None:
        """Record a stress test run."""
        self.increment_counter("stress_tests_total")
        self.increment_counter("stress_test_scenarios_total", scenarios)
        if failed > 0:
            self.increment_counter("stress_test_failures_total", failed)
        self.observe_histogram("stress_test_duration_ms", elapsed_ms)

    def record_montecarlo_simulation(self, paths: int = 0, elapsed_ms: float = 0) -> None:
        """Record a Monte Carlo simulation."""
        self.increment_counter("montecarlo_simulations_total")
        self.increment_counter("montecarlo_paths_total", paths)
        self.observe_histogram("montecarlo_simulation_duration_ms", elapsed_ms)

    def record_report_generated(self, report_type: str) -> None:
        """Record a report generation."""
        self.increment_counter("risk_reports_generated")
        self.increment_counter(f"risk_reports_{report_type}_total")

    def record_scenario_run(self, scenario_id: str) -> None:
        """Record a scenario execution."""
        self.increment_counter("scenario_runs_total")

    def update_capital_ratio(self, ratio_pct: float) -> None:
        """Update the capital ratio gauge."""
        self.set_gauge("capital_ratio", ratio_pct)

    def record_analysis_pipeline(self, elapsed_ms: float, success: bool = True) -> None:
        """Record a full analysis pipeline execution."""
        self.increment_counter("analysis_pipeline_total")
        if not success:
            self.increment_counter("analysis_pipeline_errors_total")
        self.observe_histogram("analysis_pipeline_duration_ms", elapsed_ms)

    def record_error(self, component: str, error_type: str) -> None:
        """Record a component error."""
        self.increment_counter(f"{component}_errors_total")
        self.increment_counter("analytics_errors_total")

    # ---- Export ----

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []

        for name, value in self._registry.counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")

        for name, value in self._registry.gauges.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")

        for name, values in self._registry.histograms.items():
            lines.append(f"# TYPE {name} histogram")
            stats = self.get_histogram_stats(name.replace("icyquant_", ""))
            lines.append(f"{name}_count {stats['count']}")
            lines.append(f"{name}_sum {stats['sum']}")

        return "\n".join(lines) + "\n"

    def export_dict(self) -> dict[str, Any]:
        """Export all metrics as a dictionary."""
        return {
            "counters": dict(self._registry.counters),
            "gauges": dict(self._registry.gauges),
            "histogram_stats": {
                k.replace("icyquant_", ""): self.get_histogram_stats(k.replace("icyquant_", ""))
                for k in self._registry.histograms
            },
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._registry = MetricsRegistry()
