"""Factor Discovery Gate v1 — the 16-item acceptance gate for Alpha101 pairs.

Mirrors the strategy line's ``DiscoveryGate``: every (alpha, asset) pair must
pass **all** checks; an alpha becomes a FACTOR CANDIDATE only after passing
on ``min_assets_passed`` assets.  The gate is fail-closed: missing data,
not-computable factors or missing IC blocks fail automatically.  Thresholds
come from the sealed ``factor_spec.FACTOR_GATE_THRESHOLDS`` and are never
tuned to let a factor through.

Structural checks (no look-ahead / OOS isolation / costs / slippage) are
enforced by the engine's construction — delay-1 alignment, sealed split,
always-on costs — and are reported as gate items so the evidence is recorded.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from .evaluation import SegmentIC
from .factor_backtest import PortfolioMetrics
from .factor_spec import FACTOR_GATE_THRESHOLDS


@dataclass
class FactorGateCheck:
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass
class FactorGateOutcome:
    alpha_id: str
    asset: str
    passed: bool
    fail_reason: str = ""
    checks: list[FactorGateCheck] = field(default_factory=list)
    oos_metrics: dict[str, Any] = field(default_factory=dict)

    @property
    def first_failure(self) -> Optional[FactorGateCheck]:
        for chk in self.checks:
            if not chk.passed:
                return chk
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "alpha_id": self.alpha_id,
            "asset": self.asset,
            "passed": self.passed,
            "fail_reason": self.fail_reason,
            "checks": [c.to_dict() for c in self.checks],
            "oos_metrics": self.oos_metrics,
        }


@dataclass
class PairEvidence:
    """Everything the gate needs about one (alpha, asset) pair."""

    dataset_ok: bool
    coverage: float                      # fraction of computable factor bars
    train_ic: SegmentIC
    validation_ic: SegmentIC
    oos_ic: SegmentIC
    train_pf: PortfolioMetrics
    validation_pf: PortfolioMetrics
    oos_pf: PortfolioMetrics
    wf_windows_total: int
    wf_windows_positive: int
    stability_frac: Optional[float]      # train IC sign consistency
    one_way_bps: float
    slippage_bps: float


def _same_sign(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None or a == 0 or b == 0:
        return False
    return (a > 0) == (b > 0)


class FactorGate:
    """Evaluates the 16-item Factor Discovery Gate v1."""

    CHECK_NAMES = (
        "dataset_gate",
        "factor_computable",
        "train_ic",
        "train_rank_ic",
        "train_icir",
        "train_performance",
        "validation_performance",
        "oos_performance",
        "max_drawdown",
        "turnover_cap",
        "walk_forward",
        "stability",
        "no_lookahead",
        "oos_isolated",
        "transaction_cost",
        "slippage",
    )

    def __init__(self, thresholds: Optional[dict[str, Any]] = None) -> None:
        self.t = thresholds or dict(FACTOR_GATE_THRESHOLDS)

    def evaluate(self, alpha_id: str, asset: str,
                 ev: PairEvidence) -> FactorGateOutcome:
        t = self.t
        checks: list[FactorGateCheck] = []

        def add(name: str, passed: bool, detail: str = "") -> None:
            checks.append(FactorGateCheck(name=name, passed=bool(passed),
                                          detail=detail))

        # 1. dataset
        add("dataset_gate", ev.dataset_ok,
            "bars loaded and segments non-empty" if ev.dataset_ok else "no data")
        # 2. factor computable (coverage + enough IC blocks)
        cov_ok = ev.coverage >= t["min_coverage"]
        blocks_ok = ev.train_ic.block_count >= t["min_block_count"]
        add("factor_computable", cov_ok and blocks_ok,
            f"coverage={ev.coverage:.2f} >= {t['min_coverage']}, "
            f"train blocks={ev.train_ic.block_count} >= {t['min_block_count']}")
        # 3-5. train IC family
        ic = ev.train_ic.ic
        ric = ev.train_ic.rank_ic
        icir = ev.train_ic.icir
        add("train_ic", ic is not None and abs(ic) >= t["min_abs_ic"],
            f"train IC={ic if ic is None else round(ic, 4)}")
        add("train_rank_ic", ric is not None and abs(ric) >= t["min_abs_rank_ic"],
            f"train RankIC={ric if ric is None else round(ric, 4)}")
        add("train_icir", icir is not None and abs(icir) >= t["min_abs_icir"],
            f"train ICIR={icir if icir is None else round(icir, 3)}")
        # 6. train long-short performance (net of cost)
        add("train_performance",
            ev.train_pf.sharpe >= t["min_train_sharpe"],
            f"train LS sharpe={ev.train_pf.sharpe:.2f} >= "
            f"{t['min_train_sharpe']}")
        # 7. validation: IC keeps sign & magnitude, portfolio profitable
        val_ic = ev.validation_ic.ic
        val_ok = (_same_sign(val_ic, ic)
                  and val_ic is not None and abs(val_ic) >= t["min_val_abs_ic"]
                  and ev.validation_pf.total_return > t["min_val_return"])
        add("validation_performance", val_ok,
            f"val IC={val_ic if val_ic is None else round(val_ic, 4)}, "
            f"val LS return={ev.validation_pf.total_return:.2%}")
        # 8. OOS: IC keeps sign & magnitude, portfolio keeps Sharpe
        oos_ic = ev.oos_ic.ic
        oos_ok = (_same_sign(oos_ic, ic)
                  and oos_ic is not None and abs(oos_ic) >= t["min_oos_abs_ic"]
                  and ev.oos_pf.sharpe >= t["min_oos_sharpe"])
        add("oos_performance", oos_ok,
            f"oos IC={oos_ic if oos_ic is None else round(oos_ic, 4)}, "
            f"oos LS sharpe={ev.oos_pf.sharpe:.2f} >= {t['min_oos_sharpe']}")
        # 9. max drawdown (OOS)
        add("max_drawdown", ev.oos_pf.max_drawdown >= t["max_drawdown"],
            f"oos max_dd={ev.oos_pf.max_drawdown:.2%} >= "
            f"{t['max_drawdown']:.0%}")
        # 10. turnover cap
        add("turnover_cap",
            ev.oos_pf.turnover_per_bar <= t["max_turnover_per_bar"],
            f"oos turnover/bar={ev.oos_pf.turnover_per_bar:.3f} <= "
            f"{t['max_turnover_per_bar']}")
        # 11. walk-forward (inside Train + Validation only)
        if ev.wf_windows_total > 0:
            wf_frac = ev.wf_windows_positive / ev.wf_windows_total
            wf_ok = ev.wf_windows_positive >= math.ceil(
                t["wf_min_positive_frac"] * ev.wf_windows_total)
        else:
            wf_frac = 0.0
            wf_ok = False
        add("walk_forward", wf_ok,
            f"wf windows positive={ev.wf_windows_positive}/"
            f"{ev.wf_windows_total} (frac={wf_frac:.2f})")
        # 12. stability (train IC sign consistency)
        st_ok = ev.stability_frac is not None and \
            ev.stability_frac >= 0.75
        add("stability", st_ok,
            f"quarter sign consistency="
            f"{ev.stability_frac if ev.stability_frac is None else round(ev.stability_frac, 2)}")
        # 13-14. structural invariants (engine-enforced, evidence recorded)
        add("no_lookahead", True,
            "delay-1 alignment: factor[t] predicts return t->t+1 only")
        add("oos_isolated", True,
            "OOS used only for the final measurement; walk-forward inside "
            "train+validation")
        # 15-16. costs
        add("transaction_cost", ev.one_way_bps > 0,
            f"one-way cost={ev.one_way_bps} bps")
        add("slippage", ev.slippage_bps > 0,
            f"slippage={ev.slippage_bps} bps")

        failures = [c for c in checks if not c.passed]
        return FactorGateOutcome(
            alpha_id=alpha_id,
            asset=asset,
            passed=not failures,
            fail_reason=failures[0].name if failures else "",
            checks=checks,
            oos_metrics={
                "ic": None if oos_ic is None else round(oos_ic, 4),
                "rank_ic": None if ev.oos_ic.rank_ic is None
                else round(ev.oos_ic.rank_ic, 4),
                "icir": None if ev.oos_ic.icir is None
                else round(ev.oos_ic.icir, 4),
                "sharpe": round(ev.oos_pf.sharpe, 4),
                "total_return": round(ev.oos_pf.total_return, 6),
                "max_drawdown": round(ev.oos_pf.max_drawdown, 6),
                "turnover_per_bar": round(ev.oos_pf.turnover_per_bar, 6),
                "trade_count": ev.oos_pf.trade_count,
                "blocks": ev.oos_ic.block_count,
            },
        )
