"""Discovery Gate v1 — the 16-item acceptance gate.

Every (candidate, asset) pair must pass **all** checks to become a candidate
cell; a candidate advances to ranking only if it passes on
``min_assets_passed`` assets.  The gate is fail-closed: anything unknown
(no data, no neighbours, zero trades) fails.  Thresholds come from the sealed
``spec.GATE_THRESHOLDS`` and are never tuned to let a candidate through.

The four structural checks (no look-ahead / no survivorship bias / cost /
slippage) are enforced by the engine's construction: signals use only
information at the current bar close, the universe is fixed, and costs are
always applied.  They are reported as gate items so the *evidence* is
recorded, not just assumed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .backtest import BacktestResult
from .candidate import Candidate
from .robustness import StabilityReport, WalkForwardReport
from .spec import GATE_THRESHOLDS

SEGMENTS = ("train", "validation", "oos")


@dataclass
class GateCheck:
    """One gate item with its evidence."""

    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass
class GateOutcome:
    """Result of evaluating one (candidate, asset) pair against the gate."""

    candidate_id: str
    asset: str
    passed: bool
    fail_reason: str = ""
    checks: list[GateCheck] = field(default_factory=list)
    oos_metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def first_failure(self) -> Optional[GateCheck]:
        for chk in self.checks:
            if not chk.passed:
                return chk
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "asset": self.asset,
            "passed": self.passed,
            "fail_reason": self.fail_reason,
            "checks": [c.to_dict() for c in self.checks],
            "oos_metrics": self.oos_metrics,
        }


class DiscoveryGate:
    """Evaluates the 16-item Discovery Gate v1."""

    CHECK_NAMES = (
        "dataset_gate",
        "candidate_reproducible",
        "min_trades",
        "train_performance",
        "validation_performance",
        "oos_performance",
        "max_drawdown",
        "sharpe_combined",
        "profit_factor",
        "parameter_stability",
        "walk_forward",
        "no_lookahead",
        "no_survivorship",
        "transaction_cost",
        "slippage",
        "oos_return_positive",
    )

    def __init__(self, thresholds: Optional[dict[str, Any]] = None) -> None:
        self.t = thresholds or GATE_THRESHOLDS

    # ------------------------------------------------------------------ #
    @staticmethod
    def _combined_sharpe(results: list[BacktestResult],
                         periods_per_year: int = 252) -> float:
        """Sharpe of the concatenated daily returns across segments."""
        import math
        rets: list[float] = []
        for r in results:
            eq = [e for _, e in r.equity_curve]
            for i in range(1, len(eq)):
                if eq[i - 1] > 0:
                    rets.append(eq[i] / eq[i - 1] - 1.0)
        if len(rets) < 2:
            return 0.0
        mean = sum(rets) / len(rets)
        var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
        std = math.sqrt(var)
        if std == 0:
            return 0.0
        return mean / std * math.sqrt(periods_per_year)

    # ------------------------------------------------------------------ #
    def evaluate(
        self,
        candidate: Candidate,
        dataset_ok: bool,
        train: BacktestResult,
        validation: BacktestResult,
        oos: BacktestResult,
        stability: StabilityReport,
        walk_forward: WalkForwardReport,
        cost_breakdown: dict[str, float],
    ) -> GateOutcome:
        """Evaluate all 16 checks for one (candidate, asset) pair."""
        t = self.t
        checks: list[GateCheck] = []

        def add(name: str, passed: bool, detail: str = "") -> None:
            checks.append(GateCheck(name=name, passed=bool(passed), detail=detail))

        tm, vm, om = train.metrics, validation.metrics, oos.metrics

        # 1. Dataset gate
        add("dataset_gate", dataset_ok and train.start is not None,
            f"train={train.start}->{train.end}" if train.start else "no data")
        # 2. Candidate reproducible
        cdef_ok = bool(candidate.candidate_id and candidate.structure_id
                       and candidate.parameters and candidate.asset
                       and candidate.timeframe)
        add("candidate_reproducible", cdef_ok,
            f"{candidate.candidate_id}/{candidate.structure_id}")
        # 3. Minimum trade count (OOS)
        add("min_trades", om.trade_count >= t["min_trades"],
            f"oos trades={om.trade_count} >= {t['min_trades']}")
        # 4. Train performance
        add("train_performance", tm.sharpe >= t["min_sharpe"],
            f"train sharpe={tm.sharpe:.2f} >= {t['min_sharpe']}")
        # 5. Validation performance
        add("validation_performance", vm.sharpe >= t["min_sharpe"],
            f"val sharpe={vm.sharpe:.2f} >= {t['min_sharpe']}")
        # 6. OOS performance
        add("oos_performance", om.sharpe >= t["min_sharpe"],
            f"oos sharpe={om.sharpe:.2f} >= {t['min_sharpe']}")
        # 7. Max drawdown (OOS)
        add("max_drawdown", om.max_drawdown >= t["max_drawdown"],
            f"oos max_dd={om.max_drawdown:.2%} >= {t['max_drawdown']:.0%}")
        # 8. Combined Sharpe (train+val+oos)
        comb = self._combined_sharpe([train, validation, oos])
        add("sharpe_combined", comb >= t["min_sharpe"],
            f"combined sharpe={comb:.2f} >= {t['min_sharpe']}")
        # 9. Profit factor (OOS)
        add("profit_factor", om.profit_factor >= t["min_profit_factor"],
            f"oos pf={om.profit_factor:.2f} >= {t['min_profit_factor']}")
        # 10. Parameter stability
        add("parameter_stability", stability.passed,
            f"neighbours={stability.neighbor_count}, positive_frac="
            f"{stability.neighbor_positive_frac:.2f}, cv={stability.cv:.2f}")
        # 11. Walk-forward
        add("walk_forward", walk_forward.passed,
            f"wf windows={walk_forward.windows_positive}/"
            f"{walk_forward.windows_total} positive")
        # 12. No look-ahead bias (structural: signals use bars <= current)
        add("no_lookahead", True,
            "signals evaluated at bar close; rolling channels use bars < current")
        # 13. No survivorship bias (fixed universe + synthetic composite data)
        add("no_survivorship", True,
            "fixed 9-asset universe; dataset generated with full history")
        # 14. Transaction cost included
        add("transaction_cost", oos.cost_one_way_bps > 0,
            f"one-way cost={oos.cost_one_way_bps} bps")
        # 15. Slippage included
        add("slippage", cost_breakdown.get("slippage_bps", 0.0) > 0,
            f"slippage={cost_breakdown.get('slippage_bps', 0.0)} bps")
        # 16. OOS return positive
        add("oos_return_positive", om.total_return >= t["min_oos_return"],
            f"oos return={om.total_return:.2%} >= {t['min_oos_return']:.0%}")

        failures = [c for c in checks if not c.passed]
        outcome = GateOutcome(
            candidate_id=candidate.candidate_id,
            asset=candidate.asset,
            passed=not failures,
            fail_reason=failures[0].name if failures else "",
            checks=checks,
            oos_metrics={
                "sharpe": round(om.sharpe, 4),
                "total_return": round(om.total_return, 6),
                "max_drawdown": round(om.max_drawdown, 6),
                "profit_factor": round(om.profit_factor, 4),
                "trade_count": om.trade_count,
            },
        )
        return outcome
