"""
Capacity Diagnostics — Automated health checks for the capacity system.

Detects anomalies, violations, and degradation:
- Capacity conservation violations
- Liquidity deterioration
- Impact estimation drift
- Constraint breaches
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class DiagnosticSeverity(str, Enum):
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DiagnosticType(str, Enum):
    CAPACITY_CONSERVATION = "capacity_conservation"
    LIQUIDITY_DETERIORATION = "liquidity_deterioration"
    IMPACT_DRIFT = "impact_drift"
    CONSTRAINT_VIOLATION = "constraint_violation"
    UTILIZATION_ANOMALY = "utilization_anomaly"
    OVERLAP_DETECTED = "overlap_detected"
    REGIME_ANOMALY = "regime_anomaly"
    BUDGET_BREACH = "budget_breach"
    THROTTLE_HEALTH = "throttle_health"
    MEMORY_HEALTH = "memory_health"


@dataclass
class DiagnosticReport:
    """A single diagnostic report."""

    report_id: str = field(default_factory=lambda: f"DR-{uuid.uuid4().hex[:8]}")
    diagnostic_type: DiagnosticType = DiagnosticType.CAPACITY_CONSERVATION
    severity: DiagnosticSeverity = DiagnosticSeverity.OK
    component: str = ""
    description: str = ""
    detail: str = ""
    suggestions: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_healthy(self) -> bool:
        return self.severity in (DiagnosticSeverity.OK, DiagnosticSeverity.INFO)

    @property
    def is_critical(self) -> bool:
        return self.severity == DiagnosticSeverity.CRITICAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "diagnostic_type": self.diagnostic_type.value,
            "severity": self.severity.value,
            "component": self.component,
            "description": self.description,
            "detail": self.detail,
            "suggestions": self.suggestions,
            "metrics": self.metrics,
            "is_healthy": self.is_healthy,
        }


class CapacityDiagnostics:
    """Runs automated diagnostics on the capacity management system."""

    def __init__(self):
        self._reports: List[DiagnosticReport] = []
        self._thresholds: Dict[str, float] = {
            "max_utilization": 0.95,
            "min_liquidity_score": 25.0,
            "max_impact_error_bps": 5.0,
            "max_overlap_ratio": 1.0,
            "max_breach_count": 5,
            "max_error_rate": 0.05,
        }

    # ── Diagnostics ───────────────────────────────────────────────

    def check_capacity_conservation(self,
                                      total_deployed: float,
                                      total_capacity: float,
                                      strategy_capacities: Dict[str, float]) -> DiagnosticReport:
        """Check that deployed capital <= total capacity."""
        report = DiagnosticReport(
            diagnostic_type=DiagnosticType.CAPACITY_CONSERVATION,
            component="capacity",
        )

        if total_capacity <= 0:
            report.severity = DiagnosticSeverity.WARNING
            report.description = "Total capacity is zero or negative"
            report.suggestions = ["Check capacity registration", "Verify market data availability"]
        elif total_deployed > total_capacity:
            report.severity = DiagnosticSeverity.CRITICAL
            report.description = f"Capacity conservation violated: deployed {total_deployed:,.0f} > capacity {total_capacity:,.0f}"
            report.detail = f"Violation: {(total_deployed - total_capacity):,.0f} excess"
            report.suggestions = ["Reduce position sizes", "Increase capacity limits", "Freeze deployments"]
            report.metrics["excess"] = total_deployed - total_capacity
        else:
            utilization = total_deployed / total_capacity
            if utilization > self._thresholds["max_utilization"]:
                report.severity = DiagnosticSeverity.WARNING
                report.description = f"Capacity utilization high: {utilization:.1%}"
                report.suggestions = ["Consider capacity increase", "Prepare resize policies"]
            report.metrics["utilization"] = utilization

        report.metrics.update({
            "total_deployed": total_deployed,
            "total_capacity": total_capacity,
            "strategy_count": len(strategy_capacities),
        })
        self._reports.append(report)
        return report

    def check_liquidity_deterioration(self,
                                       scores: Dict[str, float],
                                       previous_scores: Optional[Dict[str, float]] = None) -> DiagnosticReport:
        """Check for deteriorating liquidity conditions."""
        report = DiagnosticReport(
            diagnostic_type=DiagnosticType.LIQUIDITY_DETERIORATION,
            component="liquidity",
        )

        if not scores:
            report.severity = DiagnosticSeverity.INFO
            report.description = "No liquidity data available"
            self._reports.append(report)
            return report

        low_liquidity = {a: s for a, s in scores.items()
                         if s < self._thresholds["min_liquidity_score"]}
        crisis_assets = {a: s for a, s in scores.items() if s < 15.0}

        if crisis_assets:
            report.severity = DiagnosticSeverity.CRITICAL
            report.description = f"{len(crisis_assets)} assets in crisis liquidity"
            report.suggestions = ["Halt all trading", "Assess systemic risk"]
        elif low_liquidity:
            report.severity = DiagnosticSeverity.WARNING
            report.description = f"{len(low_liquidity)} assets below liquidity threshold"
            report.suggestions = ["Reduce participation", "Check market conditions"]

        if previous_scores:
            deteriorations = {
                a: previous_scores.get(a, 100.0) - scores.get(a, 100.0)
                for a in scores
                if previous_scores.get(a, 100.0) - scores.get(a, 100.0) > 20
            }
            if deteriorations:
                report.severity = DiagnosticSeverity.WARNING
                report.detail += f"\n{len(deteriorations)} assets with score drops > 20pts"
                report.metrics["worst_deterioration"] = max(deteriorations.items(), key=lambda x: x[1])

        report.metrics.update({
            "asset_count": len(scores),
            "low_liquidity_count": len(low_liquidity),
            "crisis_count": len(crisis_assets),
            "avg_score": sum(scores.values()) / len(scores) if scores else 0,
        })
        self._reports.append(report)
        return report

    def check_impact_drift(self,
                            mean_error_bps: float,
                            rmse_bps: float,
                            recent_error_count: int) -> DiagnosticReport:
        """Check for market impact model drift."""
        report = DiagnosticReport(
            diagnostic_type=DiagnosticType.IMPACT_DRIFT,
            component="impact",
        )

        if abs(mean_error_bps) > self._thresholds["max_impact_error_bps"]:
            report.severity = DiagnosticSeverity.WARNING
            report.description = f"Impact model bias detected: mean error {mean_error_bps:.2f} bps"
            report.suggestions = [
                "Re-calibrate impact model",
                "Check for regime shifts",
            ]

        if rmse_bps > self._thresholds["max_impact_error_bps"] * 2:
            report.severity = DiagnosticSeverity.ERROR
            report.description = f"Impact model variance high: RMSE {rmse_bps:.2f} bps"
            report.suggestions.append("Model may be broken — switch to conservative estimates")

        if recent_error_count < 10:
            report.severity = DiagnosticSeverity.INFO
            report.description = f"Only {recent_error_count} data points for impact calibration"

        report.metrics.update({
            "mean_error_bps": mean_error_bps,
            "rmse_bps": rmse_bps,
            "recent_error_count": recent_error_count,
        })
        self._reports.append(report)
        return report

    def check_constraint_violations(self,
                                     violations: List[Dict[str, Any]]) -> DiagnosticReport:
        """Check for active constraint violations."""
        report = DiagnosticReport(
            diagnostic_type=DiagnosticType.CONSTRAINT_VIOLATION,
            component="constraint",
        )

        if not violations:
            return report

        critical_violations = [v for v in violations if v.get("severity") == "critical"]

        if critical_violations:
            report.severity = DiagnosticSeverity.CRITICAL
            report.description = f"{len(critical_violations)} critical constraint violations"
            report.suggestions = ["Stop affected strategies", "Review limits"]
        elif len(violations) >= self._thresholds["max_breach_count"]:
            report.severity = DiagnosticSeverity.WARNING
            report.description = f"{len(violations)} constraint violations"
            report.suggestions = ["Review constraint limits", "Scale back allocations"]

        report.metrics["violation_count"] = len(violations)
        report.metrics["violations"] = violations[:10]
        self._reports.append(report)
        return report

    def check_utilization_anomaly(self,
                                   strategy_id: str,
                                   utilization: float,
                                   historical_avg: float) -> DiagnosticReport:
        """Detect anomalous utilization patterns."""
        report = DiagnosticReport(
            diagnostic_type=DiagnosticType.UTILIZATION_ANOMALY,
            component=f"strategy:{strategy_id}",
        )

        deviation = abs(utilization - historical_avg)
        if deviation > 0.3:
            report.severity = DiagnosticSeverity.WARNING
            report.description = (
                f"Strategy {strategy_id} utilization {utilization:.1%} "
                f"deviates from avg {historical_avg:.1%}"
            )
            if utilization > historical_avg:
                report.suggestions = ["Check for capacity breach", "Inspect order flow"]
            else:
                report.suggestions = ["Check if strategy is paused", "Verify data feeds"]

        report.metrics.update({
            "strategy_id": strategy_id,
            "utilization": utilization,
            "historical_avg": historical_avg,
            "deviation": deviation,
        })
        self._reports.append(report)
        return report

    def check_overlap(self,
                       asset: str,
                       strategy_count: int,
                       overlap_ratio: float) -> DiagnosticReport:
        """Check for excessive asset overlap across strategies."""
        report = DiagnosticReport(
            diagnostic_type=DiagnosticType.OVERLAP_DETECTED,
            component=f"asset:{asset}",
        )

        if overlap_ratio > self._thresholds["max_overlap_ratio"]:
            report.severity = DiagnosticSeverity.WARNING
            report.description = (
                f"Asset {asset} oversubscribed: "
                f"{strategy_count} strategies, {overlap_ratio:.1%} overlap"
            )
            report.suggestions = [
                "Reduce allocations to this asset",
                "Prioritize strategies by alpha impact",
            ]

        report.metrics.update({
            "asset": asset,
            "strategy_count": strategy_count,
            "overlap_ratio": overlap_ratio,
        })
        self._reports.append(report)
        return report

    def check_throttle_health(self,
                               throttle_active: bool,
                               throttle_rate: float,
                               duration_seconds: float) -> DiagnosticReport:
        """Check if throttle is functioning correctly."""
        report = DiagnosticReport(
            diagnostic_type=DiagnosticType.THROTTLE_HEALTH,
            component="throttle",
        )

        if throttle_active and duration_seconds > 3600:
            report.severity = DiagnosticSeverity.WARNING
            report.description = f"Throttle active for {duration_seconds:.0f}s at {throttle_rate:.1%}"
            report.suggestions = ["Check market conditions", "Consider manual override"]

        report.metrics.update({
            "throttle_active": throttle_active,
            "throttle_rate": throttle_rate,
            "duration_seconds": duration_seconds,
        })
        self._reports.append(report)
        return report

    # ── Full Health Check ─────────────────────────────────────────

    def run_full_check(self,
                        total_deployed: float,
                        total_capacity: float,
                        strategy_capacities: Dict[str, float],
                        liquidity_scores: Dict[str, float],
                        mean_impact_error: float = 0.0,
                        impact_rmse: float = 0.0,
                        impact_error_count: int = 0) -> Dict[str, DiagnosticReport]:
        """Run all diagnostics and return results keyed by type."""
        results: Dict[str, DiagnosticReport] = {}

        results["capacity_conservation"] = self.check_capacity_conservation(
            total_deployed, total_capacity, strategy_capacities
        )
        results["liquidity"] = self.check_liquidity_deterioration(liquidity_scores)
        results["impact"] = self.check_impact_drift(
            mean_impact_error, impact_rmse, impact_error_count
        )

        return results

    # ── Queries ───────────────────────────────────────────────────

    def recent_reports(self, limit: int = 50) -> List[DiagnosticReport]:
        return self._reports[-limit:]

    def critical_reports(self) -> List[DiagnosticReport]:
        return [r for r in self._reports if r.is_critical]

    def unhealthy_reports(self) -> List[DiagnosticReport]:
        return [r for r in self._reports if not r.is_healthy]

    def reports_by_type(self, diag_type: DiagnosticType) -> List[DiagnosticReport]:
        return [r for r in self._reports if r.diagnostic_type == diag_type]

    def overall_health(self) -> Tuple[bool, str]:
        """Returns (is_healthy, summary)."""
        criticals = self.critical_reports()
        errors = [r for r in self._reports if r.severity == DiagnosticSeverity.ERROR]

        if criticals:
            return False, f"CRITICAL: {len(criticals)} issue(s) — {criticals[0].description}"
        if errors:
            return False, f"ERROR: {len(errors)} issue(s)"
        return True, "All systems healthy"

    def summary(self) -> Dict[str, Any]:
        return {
            "total_reports": len(self._reports),
            "healthy": self.overall_health()[0],
            "status": self.overall_health()[1],
            "critical_count": len(self.critical_reports()),
            "unhealthy_count": len(self.unhealthy_reports()),
            "recent_unhealthy": [r.to_dict() for r in self.unhealthy_reports()[-5:]],
        }
