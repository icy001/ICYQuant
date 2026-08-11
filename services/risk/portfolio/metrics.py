"""
Portfolio Metrics — Prometheus-compatible metrics for portfolio risk.

Exposes portfolio risk score, intraday alerts, drawdown events,
PnL updates, Greeks updates, risk actions, and kill switch metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """A single metric observation."""
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = 0.0


class PortfolioMetrics:
    """
    Portfolio risk metrics collection.

    Tracks key portfolio risk indicators for monitoring and alerting.
    Uses a simple collector pattern; integrate with Prometheus client
    for production scraping.

    Metrics:
        - icyquant_portfolio_risk_score
        - icyquant_intraday_alerts_total
        - icyquant_drawdown_events_total
        - icyquant_realtime_pnl_updates
        - icyquant_greeks_updates
        - icyquant_risk_actions_total
        - icyquant_kill_switch_total

    Usage::

        metrics = PortfolioMetrics()
        metrics.record_risk_score(75.0, {"account": "ACC-01"})
        metrics.record_alert("CRITICAL", "margin")
        stats = metrics.get_all()
    """

    def __init__(self) -> None:
        # Gauges
        self._portfolio_risk_score: float = 0.0

        # Counters
        self._intraday_alerts_total: int = 0
        self._drawdown_events_total: int = 0
        self._realtime_pnl_updates: int = 0
        self._greeks_updates: int = 0
        self._risk_actions_total: int = 0
        self._kill_switch_total: int = 0

        # Labeled counters
        self._alerts_by_severity: dict[str, int] = {}
        self._alerts_by_type: dict[str, int] = {}
        self._actions_by_type: dict[str, int] = {}
        self._drawdown_by_period: dict[str, int] = {}

        # Failure counters
        self._evaluation_failures: int = 0
        self._monitor_failures: int = 0
        self._action_failures: int = 0
        self._alert_dispatch_failures: int = 0
        self._health_check_failures: int = 0

    # ---- Gauge Updates ----

    def set_risk_score(self, score: float) -> None:
        """Set current portfolio risk score (gauge)."""
        self._portfolio_risk_score = score

    # ---- Counter Updates ----

    def record_risk_score(self, score: float, labels: dict[str, str] = None) -> None:
        """Record a risk score observation."""
        self._portfolio_risk_score = score
        logger.debug(f"Metric: portfolio_risk_score={score}")

    def record_alert(self, severity: str, alert_type: str) -> None:
        """Record an intraday alert."""
        self._intraday_alerts_total += 1
        self._alerts_by_severity[severity] = self._alerts_by_severity.get(severity, 0) + 1
        self._alerts_by_type[alert_type] = self._alerts_by_type.get(alert_type, 0) + 1

    def record_drawdown_event(self, period: str) -> None:
        """Record a drawdown event."""
        self._drawdown_events_total += 1
        self._drawdown_by_period[period] = self._drawdown_by_period.get(period, 0) + 1

    def record_pnl_update(self) -> None:
        """Record a real-time PnL update."""
        self._realtime_pnl_updates += 1

    def record_greeks_update(self) -> None:
        """Record a Greeks computation update."""
        self._greeks_updates += 1

    def record_risk_action(self, action_type: str) -> None:
        """Record a risk action execution."""
        self._risk_actions_total += 1
        self._actions_by_type[action_type] = self._actions_by_type.get(action_type, 0) + 1

    def record_kill_switch(self) -> None:
        """Record a kill switch activation."""
        self._kill_switch_total += 1

    # ---- Failure Counters ----

    def record_evaluation_failure(self) -> None:
        self._evaluation_failures += 1

    def record_monitor_failure(self) -> None:
        self._monitor_failures += 1

    def record_action_failure(self) -> None:
        self._action_failures += 1

    def record_alert_dispatch_failure(self) -> None:
        self._alert_dispatch_failures += 1

    def record_health_check_failure(self) -> None:
        self._health_check_failures += 1

    # ---- Export ----

    def get_all(self) -> dict[str, Any]:
        """Export all metrics as a dict."""
        return {
            "gauges": {
                "icyquant_portfolio_risk_score": self._portfolio_risk_score,
            },
            "counters": {
                "icyquant_intraday_alerts_total": self._intraday_alerts_total,
                "icyquant_drawdown_events_total": self._drawdown_events_total,
                "icyquant_realtime_pnl_updates": self._realtime_pnl_updates,
                "icyquant_greeks_updates": self._greeks_updates,
                "icyquant_risk_actions_total": self._risk_actions_total,
                "icyquant_kill_switch_total": self._kill_switch_total,
            },
            "labeled": {
                "alerts_by_severity": dict(self._alerts_by_severity),
                "alerts_by_type": dict(self._alerts_by_type),
                "actions_by_type": dict(self._actions_by_type),
                "drawdown_by_period": dict(self._drawdown_by_period),
            },
            "failures": {
                "evaluation_failures": self._evaluation_failures,
                "monitor_failures": self._monitor_failures,
                "action_failures": self._action_failures,
                "alert_dispatch_failures": self._alert_dispatch_failures,
                "health_check_failures": self._health_check_failures,
            },
        }

    def get_prometheus_format(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []

        # Gauges
        lines.append(f"icyquant_portfolio_risk_score {self._portfolio_risk_score}")

        # Counters
        lines.append(f"icyquant_intraday_alerts_total {self._intraday_alerts_total}")
        lines.append(f"icyquant_drawdown_events_total {self._drawdown_events_total}")
        lines.append(f"icyquant_realtime_pnl_updates {self._realtime_pnl_updates}")
        lines.append(f"icyquant_greeks_updates {self._greeks_updates}")
        lines.append(f"icyquant_risk_actions_total {self._risk_actions_total}")
        lines.append(f"icyquant_kill_switch_total {self._kill_switch_total}")

        # Labeled
        for sev, count in self._alerts_by_severity.items():
            lines.append(f'icyquant_alerts_by_severity{{severity="{sev}"}} {count}')

        for atype, count in self._actions_by_type.items():
            lines.append(f'icyquant_actions_by_type{{action_type="{atype}"}} {count}')

        # Failures
        lines.append(f"icyquant_evaluation_failures_total {self._evaluation_failures}")
        lines.append(f"icyquant_monitor_failures_total {self._monitor_failures}")
        lines.append(f"icyquant_action_failures_total {self._action_failures}")

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self._portfolio_risk_score = 0.0
        self._intraday_alerts_total = 0
        self._drawdown_events_total = 0
        self._realtime_pnl_updates = 0
        self._greeks_updates = 0
        self._risk_actions_total = 0
        self._kill_switch_total = 0
        self._alerts_by_severity.clear()
        self._alerts_by_type.clear()
        self._actions_by_type.clear()
        self._drawdown_by_period.clear()
        self._evaluation_failures = 0
        self._monitor_failures = 0
        self._action_failures = 0
        self._alert_dispatch_failures = 0
        self._health_check_failures = 0
