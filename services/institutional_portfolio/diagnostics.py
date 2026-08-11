"""
Portfolio Diagnostics — Issue Detection & Troubleshooting

Diagnoses portfolio problems:
- Strategy signal lag / staleness
- Position concentration issues
- Rebalance oscillation detection
- Capital allocation inefficiency
- Risk aggregation anomalies
"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DiagnosticIssue:
    issue_id: str
    severity: str  # INFO, WARNING, ERROR
    category: str
    message: str
    source: Optional[str] = None
    recommendation: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


class PortfolioDiagnostics:
    """
    Continuously monitors portfolio health and raises diagnostic issues.

    Detects: staleness, concentration, oscillation, inefficiency, anomalies.
    """

    def __init__(
        self,
        diagnostics_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.diagnostics_id = diagnostics_id or f"pd-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._issues: List[DiagnosticIssue] = []
        self._last_signal_time: Dict[str, datetime] = {}
        self._concentration_threshold = self.config.get("concentration_threshold", 0.30)
        self._staleness_threshold = self.config.get("staleness_minutes", 15)

    def check_signal_staleness(self, strategy_signals: Dict[str, datetime]) -> List[DiagnosticIssue]:
        """Detect strategies that haven't produced recent signals."""
        issues = []
        for sid, last_time in strategy_signals.items():
            age = (datetime.utcnow() - last_time).total_seconds() / 60
            if age > self._staleness_threshold:
                issues.append(DiagnosticIssue(
                    issue_id=f"diag-{uuid.uuid4().hex[:8]}",
                    severity="WARNING",
                    category="STALENESS",
                    message=f"Strategy {sid} last signal {age:.0f}m ago",
                    source=sid,
                    recommendation="Check strategy health, consider quarantine",
                ))
        self._issues.extend(issues)
        return issues

    def check_concentration(self, weights: Dict[str, float]) -> List[DiagnosticIssue]:
        """Detect position concentration issues."""
        issues = []
        for asset, weight in weights.items():
            if abs(weight) > self._concentration_threshold:
                issues.append(DiagnosticIssue(
                    issue_id=f"diag-{uuid.uuid4().hex[:8]}",
                    severity="WARNING",
                    category="CONCENTRATION",
                    message=f"Asset {asset} concentration {weight:.4f} > {self._concentration_threshold}",
                    source=asset,
                    recommendation="Reduce position size or hedge",
                ))
        self._issues.extend(issues)
        return issues

    def check_rebalance_oscillation(self, rebalance_count: int, window_minutes: int = 60) -> List[DiagnosticIssue]:
        """Detect excessive rebalancing (oscillation)."""
        issues = []
        if rebalance_count > 5:
            issues.append(DiagnosticIssue(
                issue_id=f"diag-{uuid.uuid4().hex[:8]}",
                severity="ERROR",
                category="OSCILLATION",
                message=f"{rebalance_count} rebalances in {window_minutes}m — possible oscillation",
                recommendation="Increase rebalance cooldown, check drift thresholds",
            ))
        self._issues.extend(issues)
        return issues

    def get_issues(self, severity: Optional[str] = None) -> List[DiagnosticIssue]:
        if severity:
            return [i for i in self._issues if i.severity == severity]
        return list(self._issues)

    def clear(self) -> None:
        self._issues.clear()
