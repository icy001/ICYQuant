from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ExposureBreakdown:
    by_sector: Dict[str, float]
    by_country: Dict[str, float]
    by_currency: Dict[str, float]
    by_asset_class: Dict[str, float]
    by_strategy: Dict[str, float]
    by_agent: Dict[str, float]


@dataclass
class ExposureReport:
    total_exposure: float
    used_risk_budget_pct: float
    remaining_budget_pct: float
    breakdown: ExposureBreakdown
    violations: List[str]


class ExposureEngine:
    def __init__(self, total_risk_budget: float = 1.0):
        self.total_risk_budget = total_risk_budget
        self.sector_limits: Dict[str, float] = {}
        self.strategy_limits: Dict[str, float] = {}
        self.agent_limits: Dict[str, float] = {}

    def set_limits(
        self,
        sector_limits: Dict[str, float] = None,
        strategy_limits: Dict[str, float] = None,
        agent_limits: Dict[str, float] = None,
    ):
        if sector_limits:
            self.sector_limits = sector_limits
        if strategy_limits:
            self.strategy_limits = strategy_limits
        if agent_limits:
            self.agent_limits = agent_limits

    def calculate_used_budget(self, breakdown: Dict[str, float]) -> float:
        return sum(breakdown.values())

    def check_violations(self, breakdown: Dict[str, float], limits: Dict[str, float]) -> List[str]:
        violations = []
        for entity, exposure in breakdown.items():
            limit = limits.get(entity, self.total_risk_budget)
            if exposure > limit:
                violations.append(f"{entity}: {exposure:.2%} > {limit:.2%}")
        return violations

    def generate_report(
        self,
        sector_exposure: Dict[str, float],
        country_exposure: Dict[str, float] = None,
        currency_exposure: Dict[str, float] = None,
        asset_exposure: Dict[str, float] = None,
        strategy_exposure: Dict[str, float] = None,
        agent_exposure: Dict[str, float] = None,
    ) -> ExposureReport:
        country_exposure = country_exposure or {}
        currency_exposure = currency_exposure or {}
        asset_exposure = asset_exposure or {}
        strategy_exposure = strategy_exposure or {}
        agent_exposure = agent_exposure or {}

        total = sum(sector_exposure.values())
        used_pct = total / self.total_risk_budget if self.total_risk_budget > 0 else 0
        remaining = max(0, 1.0 - used_pct)

        violations = []
        violations.extend(
            self.check_violations(sector_exposure, self.sector_limits)
        )
        violations.extend(
            self.check_violations(strategy_exposure, self.strategy_limits)
        )
        violations.extend(
            self.check_violations(agent_exposure, self.agent_limits)
        )

        breakdown = ExposureBreakdown(
            by_sector=sector_exposure,
            by_country=country_exposure,
            by_currency=currency_exposure,
            by_asset_class=asset_exposure,
            by_strategy=strategy_exposure,
            by_agent=agent_exposure,
        )

        return ExposureReport(
            total_exposure=round(total, 4),
            used_risk_budget_pct=round(used_pct, 4),
            remaining_budget_pct=round(remaining, 4),
            breakdown=breakdown,
            violations=violations,
        )

    def can_allocate(self, entity: str, requested_pct: float, limits: Dict[str, float]) -> bool:
        current = sum(
            v for k, v in limits.items() if k == entity
        )
        limit = limits.get(entity, self.total_risk_budget)
        return (current + requested_pct) <= limit
