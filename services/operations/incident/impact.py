"""Incident impact model (Commit 27 Part 1.4, spec sections 6-7, 18-20).

Alert 只告诉你 "execution latency > 100ms"，
Incident 必须告诉你 "这到底影响了什么":

    Execution latency
        ↓
    NASDAQ
        ↓
    3 strategies
        ↓
    42 orders
        ↓
    $1.25M exposure
"""

from __future__ import annotations

from dataclasses import dataclass

from .severity import IncidentSeverity


@dataclass(frozen=True)
class IncidentImpact:

    affected_services: tuple[str, ...]

    affected_venues: tuple[str, ...]

    affected_strategies: tuple[str, ...]

    affected_orders: int

    affected_positions: int

    trading_blocked: bool

    capital_at_risk: float = 0.0

    description: str = ""


class ImpactCalculator:

    def calculate(
        self,
        affected_services,
        affected_orders=0,
        affected_positions=0,
        trading_blocked=False,
        capital_at_risk=0.0,
    ):

        return IncidentImpact(
            affected_services=tuple(
                affected_services
            ),
            affected_venues=(),
            affected_strategies=(),
            affected_orders=affected_orders,
            affected_positions=affected_positions,
            trading_blocked=trading_blocked,
            capital_at_risk=capital_at_risk,
        )


def assess_severity(
    impact: IncidentImpact,
) -> IncidentSeverity:
    """根据 Impact 的确定性严重级别规则 (spec section 20)。

        No trading impact                          -> MINOR
        One non-critical service                   -> MODERATE
        Strategy impacted                          -> MAJOR
        Trading blocked / position inconsistency   -> CRITICAL
        Global trading safety compromised          -> CATASTROPHIC
    """

    if impact.trading_blocked:
        if (
            impact.affected_positions > 0
            and impact.capital_at_risk > 0
        ):
            return IncidentSeverity.CATASTROPHIC
        return IncidentSeverity.CRITICAL

    if impact.affected_positions > 0:
        return IncidentSeverity.CRITICAL

    if impact.affected_strategies:
        return IncidentSeverity.MAJOR

    if len(impact.affected_services) >= 1:
        return IncidentSeverity.MODERATE

    return IncidentSeverity.MINOR
