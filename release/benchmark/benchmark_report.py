"""
Benchmark report generator for aggregating and presenting benchmark results.

Generates comprehensive benchmark reports in markdown and JSON formats,
includes comparison with baseline metrics, and tracks pass/fail against
SLA thresholds.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class SLATHreshold:
    name: str
    warning_threshold: float
    critical_threshold: float
    unit: str = "ms"


@dataclass
class BenchmarkReport:
    title: str = "ICYQuant Benchmark Report"
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    results: dict[str, Any] = field(default_factory=dict)
    baselines: dict[str, Any] = field(default_factory=dict)
    sla_thresholds: dict[str, SLATHreshold] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)

    def add_result(self, name: str, result: Any) -> None:
        self.results[name] = result

    def add_baseline(self, name: str, baseline: Any) -> None:
        self.baselines[name] = baseline

    def add_sla_threshold(
        self,
        name: str,
        warning: float,
        critical: float,
        unit: str = "ms",
    ) -> None:
        self.sla_thresholds[name] = SLATHreshold(
            name=name,
            warning_threshold=warning,
            critical_threshold=critical,
            unit=unit,
        )

    def compare_with_baseline(self, name: str) -> Optional[dict[str, Any]]:
        if name not in self.results or name not in self.baselines:
            return None

        result = self._to_dict(self.results[name])
        baseline = self._to_dict(self.baselines[name])

        comparison: dict[str, Any] = {"name": name, "metrics": {}}

        for key in result:
            if key in baseline and isinstance(result[key], (int, float)):
                current_val = result[key]
                baseline_val = baseline[key]
                if baseline_val != 0:
                    delta = current_val - baseline_val
                    change_pct = (delta / baseline_val) * 100.0
                    comparison["metrics"][key] = {
                        "current": current_val,
                        "baseline": baseline_val,
                        "delta": delta,
                        "change_percent": round(change_pct, 2),
                    }

        return comparison

    def check_sla(self, name: str) -> dict[str, Any]:
        if name not in self.results or name not in self.sla_thresholds:
            return {"status": "unknown", "reason": "No SLA threshold defined"}

        threshold = self.sla_thresholds[name]
        result_dict = self._to_dict(self.results[name])

        checks: list[dict[str, Any]] = []
        overall_status = "pass"

        for key, value in result_dict.items():
            if isinstance(value, (int, float)):
                if value >= threshold.critical_threshold:
                    checks.append({
                        "metric": key,
                        "value": value,
                        "threshold": threshold.critical_threshold,
                        "level": "critical",
                    })
                    overall_status = "fail"
                elif value >= threshold.warning_threshold:
                    checks.append({
                        "metric": key,
                        "value": value,
                        "threshold": threshold.warning_threshold,
                        "level": "warning",
                    })
                    if overall_status != "fail":
                        overall_status = "warning"

        return {
            "name": name,
            "status": overall_status,
            "checks": checks,
        }

    def generate_markdown(self) -> str:
        lines: list[str] = []

        lines.append(f"# {self.title}")
        lines.append("")
        lines.append(f"**Generated**: {self.generated_at}")
        lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append("| Benchmark | Status | SLA |")
        lines.append("|-----------|--------|-----|")

        for name in self.results:
            sla_status = self.check_sla(name)
            status_icon = self._status_icon(sla_status.get("status", "unknown"))
            lines.append(f"| {name} | {status_icon} | {sla_status.get('status', 'N/A')} |")

        lines.append("")

        if self.baselines:
            lines.append("## Comparison with Baseline")
            lines.append("")
            for name in self.results:
                comparison = self.compare_with_baseline(name)
                if comparison:
                    lines.append(f"### {name}")
                    lines.append("")
                    lines.append("| Metric | Current | Baseline | Delta | Change |")
                    lines.append("|--------|---------|----------|-------|--------|")
                    for metric, data in comparison["metrics"].items():
                        sign = "+" if data["delta"] >= 0 else ""
                        lines.append(
                            f"| {metric} | {data['current']:.2f} | {data['baseline']:.2f} | "
                            f"{sign}{data['delta']:.2f} | {sign}{data['change_percent']}% |"
                        )
                    lines.append("")

        lines.append("## Detailed Results")
        lines.append("")
        for name, result in self.results.items():
            lines.append(f"### {name}")
            lines.append("")
            result_dict = self._to_dict(result)
            for key, value in result_dict.items():
                if isinstance(value, list) and len(value) > 0:
                    lines.append(f"- **{key}**: {len(value)} items")
                elif isinstance(value, dict):
                    lines.append(f"- **{key}**: {json.dumps(value, default=str)[:200]}")
                else:
                    lines.append(f"- **{key}**: {value}")
            lines.append("")

        if self.recommendations:
            lines.append("## Recommendations")
            lines.append("")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")
            lines.append("")

        return "\n".join(lines)

    def generate_json(self) -> str:
        data: dict[str, Any] = {
            "title": self.title,
            "generated_at": self.generated_at,
            "results": {},
            "baselines": {},
            "sla_checks": {},
            "comparisons": {},
            "recommendations": self.recommendations,
        }

        for name, result in self.results.items():
            data["results"][name] = self._to_dict(result)

        for name, baseline in self.baselines.items():
            data["baselines"][name] = self._to_dict(baseline)

        for name in self.results:
            data["sla_checks"][name] = self.check_sla(name)

        for name in self.results:
            comparison = self.compare_with_baseline(name)
            if comparison:
                data["comparisons"][name] = comparison

        return json.dumps(data, indent=2, default=str, ensure_ascii=False)

    def add_recommendation(self, recommendation: str) -> None:
        self.recommendations.append(recommendation)

    def _to_dict(self, obj: Any) -> dict[str, Any]:
        if hasattr(obj, "__dataclass_fields__"):
            result: dict[str, Any] = {}
            for field_name in obj.__dataclass_fields__:
                value = getattr(obj, field_name)
                if hasattr(value, "__dataclass_fields__"):
                    result[field_name] = self._to_dict(value)
                elif isinstance(value, list):
                    result[field_name] = [
                        self._to_dict(item) if hasattr(item, "__dataclass_fields__") else item
                        for item in value
                    ]
                elif isinstance(value, dict):
                    result[field_name] = {
                        k: self._to_dict(v) if hasattr(v, "__dataclass_fields__") else v
                        for k, v in value.items()
                    }
                else:
                    result[field_name] = value
            return result
        elif isinstance(obj, dict):
            return obj
        else:
            return {"value": obj}

    @staticmethod
    def _status_icon(status: str) -> str:
        icons = {
            "pass": "✅",
            "warning": "⚠️",
            "fail": "❌",
            "unknown": "❓",
        }
        return icons.get(status, "❓")