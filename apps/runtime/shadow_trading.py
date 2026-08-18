"""Phase 5 - Shadow Trading: mirror live signals in parallel, touch nothing real.

A signal stream is fed to BOTH:
    * the reference (production-track) pipeline, and
    * an isolated shadow pipeline using its own engine instances and its
      own virtual account.

The session then compares every signal's outcome and the final state of
both tracks, reporting divergences. The shadow track is fully isolated:
no shared stores, no shared engines, no real capital.

Feature Freeze: reuses TradingPipeline unchanged; only the harness is new.

Report fields:
    mirrored_signals   - total signals mirrored
    consistent         - outcomes identical in both tracks
    divergences        - list of per-signal differences
    reference_state    - final positions/ledger of the reference track
    shadow_state       - final positions/ledger of the shadow track
    all_consistent     - gate boolean
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from apps.runtime.pipeline import PipelineResult, Signal, TradingPipeline

logger = logging.getLogger(__name__)


@dataclass
class ShadowSignal:
    """A signal as observed on the live stream."""

    symbol: str
    side: str
    quantity: int
    price: Optional[float] = None


@dataclass
class ShadowReport:
    mirrored_signals: int = 0
    consistent: int = 0
    divergences: list[dict] = field(default_factory=list)
    reference_state: dict = field(default_factory=dict)
    shadow_state: dict = field(default_factory=dict)

    @property
    def all_consistent(self) -> bool:
        return self.mirrored_signals > 0 and self.consistent == self.mirrored_signals


class ShadowTradingSession:
    """Mirrors a signal stream against an isolated shadow track."""

    def __init__(self, signal_source: Callable[[], list[ShadowSignal]]) -> None:
        self.signal_source = signal_source
        # Reference = production track (its own engine instances)
        self.reference = TradingPipeline()
        # Shadow = fully isolated track (independent engine instances)
        self.shadow = TradingPipeline()
        self.report = ShadowReport()

    # ------------------------------------------------------------------
    def _execute(self, pipeline: TradingPipeline, sig: ShadowSignal) -> PipelineResult:
        result: PipelineResult = pipeline.submit_signal(
            Signal(symbol=sig.symbol, side=sig.side, quantity=sig.quantity, price=sig.price)
        )
        if result.execution_reason == "risk_rejected" or not result.order_id:
            return result
        exec_price = sig.price or 0.0
        if exec_price == 0.0:
            return result
        pipeline.fill_order(result, sig.quantity, float(exec_price))
        return result

    def _outcome(self, result: PipelineResult) -> dict:
        return {
            "order_status": result.order_status,
            "filled": result.filled_quantity,
            "reason": result.execution_reason,
        }

    def _positions(self, pipeline: TradingPipeline) -> dict:
        return {k: v.quantity for k, v in pipeline.position_repo.positions.items()}

    # ------------------------------------------------------------------
    def run(self) -> ShadowReport:
        signals = self.signal_source()
        for sig in signals:
            ref_result = self._execute(self.reference, sig)
            shadow_result = self._execute(self.shadow, sig)

            ref_out = self._outcome(ref_result)
            shadow_out = self._outcome(shadow_result)
            if ref_out == shadow_out:
                self.report.consistent += 1
            else:
                self.report.divergences.append(
                    {
                        "symbol": sig.symbol,
                        "side": sig.side,
                        "quantity": sig.quantity,
                        "reference": ref_out,
                        "shadow": shadow_out,
                    }
                )
            self.report.mirrored_signals += 1

        self.report.reference_state = {
            "positions": self._positions(self.reference),
            "ledger_events": self.reference.ledger["count"],
        }
        self.report.shadow_state = {
            "positions": self._positions(self.shadow),
            "ledger_events": self.shadow.ledger["count"],
        }
        return self.report
