"""
Governance Diagnostics — subsystem health and diagnostic tools.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .governance_engine import GovernanceEngine
from .governance_manager import GovernanceManager
from .policy_engine import PolicyEngine
from .authority_engine import AuthorityEngine
from .decision_audit import DecisionAudit
from .governance_event_store import GovernanceEventStore


class GovernanceDiagnostics:
    """
    Diagnostic tools for the governance subsystem.
    Provides health checks, bottleneck analysis, and configuration validation.
    """

    def __init__(
        self,
        engine: Optional[GovernanceEngine] = None,
        manager: Optional[GovernanceManager] = None,
    ):
        self._engine = engine
        self._manager = manager

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Run a comprehensive governance health check."""
        checks = {
            "timestamp": time.time(),
            "overall": "HEALTHY",
            "components": {},
        }

        # Check manager
        if self._manager:
            mgr_snapshot = self._manager.get_snapshot()
            checks["components"]["manager"] = {
                "status": "RUNNING" if mgr_snapshot.get("started") else "STOPPED",
                "enabled": mgr_snapshot.get("enabled", False),
                "policies_count": mgr_snapshot.get("policies_count", 0),
                "audit_records": mgr_snapshot.get("audit_records", 0),
            }
            runtime = mgr_snapshot.get("runtime", {})
            checks["components"]["runtime"] = runtime

        # Check policy engine
        if self._engine:
            try:
                policies = self._engine._policy_engine.list_policies()
                active = [p for p in policies if p.enabled]
                checks["components"]["policy_engine"] = {
                    "status": "OK",
                    "total_policies": len(policies),
                    "active_policies": len(active),
                }
            except Exception as exc:
                checks["components"]["policy_engine"] = {
                    "status": "ERROR",
                    "error": str(exc),
                }

        # Check authority engine
        if self._engine:
            try:
                authorities = self._engine._authority_engine.list_authorities()
                checks["components"]["authority_engine"] = {
                    "status": "OK",
                    "authorities_count": len(authorities),
                }
            except Exception as exc:
                checks["components"]["authority_engine"] = {
                    "status": "ERROR",
                    "error": str(exc),
                }

        # Determine overall
        statuses = [c.get("status", "UNKNOWN") for c in checks["components"].values()]
        if "ERROR" in statuses:
            checks["overall"] = "DEGRADED"
        elif "STOPPED" in statuses:
            checks["overall"] = "WARNING"

        return checks

    # ------------------------------------------------------------------
    # Configuration validation
    # ------------------------------------------------------------------

    def validate_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate governance configuration."""
        issues = []
        warnings = []

        # Check essential policies
        policies = config.get("policies", [])
        policy_ids = {p.get("policy_id", "") for p in policies if isinstance(p, dict)}

        essential = {
            "default-max-allocation": "Maximum allocation policy",
            "default-max-leverage": "Maximum leverage policy",
            "default-min-survival": "Minimum survival policy",
            "default-risk-budget": "Risk budget policy",
        }

        for pid, desc in essential.items():
            if pid not in policy_ids:
                warnings.append(f"Missing essential policy: {desc}")

        # Check authority setup
        authorities = config.get("authorities", [])
        if not authorities:
            issues.append("No authorities configured — all decisions will be denied")

        # Check approval thresholds
        approval_reqs = config.get("approval_requirements", [])
        if not approval_reqs:
            warnings.append("No approval requirements configured — all decisions auto-approved")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "policies_count": len(policies),
            "authorities_count": len(authorities),
            "approval_requirements_count": len(approval_reqs),
        }

    # ------------------------------------------------------------------
    # Bottleneck analysis
    # ------------------------------------------------------------------

    def analyze_performance(self, telemetry: Optional[Any] = None) -> Dict[str, Any]:
        """Analyze governance pipeline performance bottlenecks."""
        if telemetry is None:
            return {"error": "No telemetry data available"}

        breakdown = telemetry.get_breakdown() if hasattr(telemetry, "get_breakdown") else {}

        # Find slowest segment
        slowest = sorted(breakdown.items(), key=lambda x: x[1], reverse=True)

        return {
            "avg_total_latency_ms": telemetry.avg_latency() if hasattr(telemetry, "avg_latency") else 0,
            "segment_breakdown": breakdown,
            "bottleneck": slowest[0] if slowest else None,
            "recommendations": self._generate_recommendations(slowest),
        }

    @staticmethod
    def _generate_recommendations(slowest_segments: List[tuple]) -> List[str]:
        recommendations = []
        for seg, lat in slowest_segments[:3]:
            if lat > 50:
                recommendations.append(
                    f"Segment '{seg}' is slow ({lat:.1f}ms avg) — consider optimization"
                )
        return recommendations

    # ------------------------------------------------------------------
    # Decision audit analysis
    # ------------------------------------------------------------------

    def analyze_decisions(self, auditor: Optional[DecisionAudit] = None) -> Dict[str, Any]:
        """Analyze decision patterns."""
        if auditor is None:
            if self._manager:
                auditor = self._manager.auditor
            else:
                return {"error": "No auditor available"}

        stats = auditor.stats()

        # Acceptance rate
        total = stats.get("total", 0)
        verdicts = stats.get("verdicts", {})
        allowed = verdicts.get("ALLOW", 0)
        blocked = verdicts.get("BLOCKED", 0)
        rejected = verdicts.get("REJECT", 0)

        acceptance_rate = allowed / total if total > 0 else 0.0

        # Override rate
        overrides = stats.get("overrides", 0)
        override_rate = overrides / total if total > 0 else 0.0

        # Top blocking reasons
        blocked_decisions = auditor.get_blocked_decisions(limit=50)
        reason_counts: Dict[str, int] = {}
        for d in blocked_decisions:
            reason = d.get("reason", "")[:60]
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        top_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_decisions": total,
            "acceptance_rate": acceptance_rate,
            "override_rate": override_rate,
            "verdicts": verdicts,
            "top_block_reasons": [{"reason": r, "count": c} for r, c in top_reasons],
            "overrides_count": overrides,
        }
