"""Single source of truth for transaction-cost assumptions.

WHY THIS MODULE EXISTS
----------------------
Cost assumptions had spread across the repository in three incompatible
forms, which is how the same strategy ended up quoted at both netPF 1.338
and 1.289 depending on which note you read:

  1. pip-denominated constants, one per experiment script
     (COST_PIPS = 1.0, COST_PIPS = 1.5, COST_PIPS_CHANGE = 0.75, ...)
  2. CLI defaults buried in argument parsers
     (--cost-pips default=1.5)
  3. a bps-denominated config used by the Discovery Lab engine
     (spec.COST_CONFIG, consumed by cost.CostModel)

Forms 1 and 3 disagree for EURUSD by roughly 3x. That is not a bug in
either one -- they were written for different purposes at different times
-- but nothing in the code made the disagreement visible, so numbers from
the two worlds were compared directly.

THE RULE
--------
* New research code takes its cost from this module, never a literal.
* Historical numbers are NOT rewritten. A report that says 1.5 pip was
  produced under a 1.5 pip assumption; silently changing it would falsify
  a published result. Instead the constant carries a docstring explaining
  what it meant and whether it still applies.
* When quoting performance, always state the denomination and the value,
  e.g. "netPF 1.338 @ 1.0 pip RT".
"""

from __future__ import annotations

from dataclasses import dataclass


# --------------------------------------------------------------------------- #
# 1. pip-denominated assumptions (research scripts, account reality)
# --------------------------------------------------------------------------- #

# The account actually held during this project: swap-free, EURUSD spread
# 5 USD per lot per side => 1.0 pip round trip. This is the number every
# "is it tradable" decision was made against.
ACCOUNT_EURUSD_RT_PIPS: float = 1.0

# Legacy assumption used by exp01-exp05 and the reversal_v1 line, before the
# real account terms were measured. Documented in those reports as
# "ASSUMED; data is single-sided bid". Kept for reproducing history only --
# it is NOT the account and must not be used for a go/no-go decision.
LEGACY_ASSUMED_RT_PIPS: float = 1.5

# exp06 charged per position change rather than per round trip.
LEGACY_RT_PIPS_ON_FLIP: float = 1.5
LEGACY_PER_CHANGE_PIPS: float = 0.75   # = 1.5 / 2, symmetric flip

# Break-even thresholds are a property of a strategy, not of an account.
# Recorded here so nobody re-derives them inconsistently.
BREAK_EVEN_PIPS: dict[str, float] = {
    # 0.3328 pip gross per trade, 1962 trades/yr
    "m5_reversal_h12": 0.333,
    # ~110 pip target, 10.4 trades/yr
    "tp_to_open": 4.66,
}


# --------------------------------------------------------------------------- #
# 2. Unit conversion
# --------------------------------------------------------------------------- #

def bps_to_pips(bps: float, price: float) -> float:
    """Convert basis points of notional to pips at a given FX price.

    EURUSD quotes to 4 decimals, so one pip is 0.0001 in price terms, i.e.
    0.0001 / price of notional. At price 1.08, 1 pip is about 0.926 bps --
    which is why "3 bps" and "3 pips" are not interchangeable and why the
    EURUSD discrepancy below is material rather than cosmetic.
    """
    if price <= 0:
        raise ValueError("price must be positive")
    return bps * price / 10_000.0 / 0.0001


def pips_to_bps(pips: float, price: float) -> float:
    """Inverse of :func:`bps_to_pips`."""
    if price <= 0:
        raise ValueError("price must be positive")
    return pips * 0.0001 / price * 10_000.0


# --------------------------------------------------------------------------- #
# 3. Discovery Lab (bps) vs research scripts (pip) reconciliation
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class CostDenominationMismatch:
    """Documents a known disagreement between two cost conventions."""

    asset: str
    discovery_round_trip_bps: float
    account_round_trip_pips: float
    price_reference: float

    @property
    def discovery_round_trip_pips(self) -> float:
        return bps_to_pips(self.discovery_round_trip_bps, self.price_reference)

    @property
    def ratio(self) -> float:
        """How many times more conservative the Discovery assumption is."""
        return self.discovery_round_trip_pips / self.account_round_trip_pips

    def describe(self) -> str:
        return (
            f"{self.asset}: Discovery {self.discovery_round_trip_bps:g} bps "
            f"= {self.discovery_round_trip_pips:.2f} pip at {self.price_reference:g}, "
            f"vs account {self.account_round_trip_pips:g} pip RT "
            f"({self.ratio:.1f}x more conservative)"
        )


# spec.COST_CONFIG gives EURUSD commission 0.0 + spread 1.0 + slippage 0.5
# = 1.5 bps one way, 3.0 bps round trip. At the 2000-2026 average price near
# 1.08 that is ~3.24 pip, against the account's measured 1.0 pip.
#
# Interpretation, stated plainly: the Discovery engine is CONSERVATIVE for
# EURUSD, not wrong. A candidate that survives it would survive the real
# account too. But a Discovery net-PF and a research-script net-PF for
# EURUSD are not comparable, and no conclusion may cross between them
# without restating the cost.
KNOWN_MISMATCHES: tuple[CostDenominationMismatch, ...] = (
    CostDenominationMismatch(
        asset="EURUSD",
        discovery_round_trip_bps=3.0,
        account_round_trip_pips=ACCOUNT_EURUSD_RT_PIPS,
        price_reference=1.08,
    ),
)


def describe_all_mismatches() -> list[str]:
    return [m.describe() for m in KNOWN_MISMATCHES]
