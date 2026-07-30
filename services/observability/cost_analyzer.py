from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict


@dataclass
class CostEntry:
    resource_type: str
    resource_name: str
    amount: float
    currency: str
    units: float
    unit_price: float
    timestamp: datetime
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class CostBreakdown:
    category: str
    total_amount: float
    currency: str
    entries_count: int
    period_start: datetime
    period_end: datetime
    details: List[CostEntry] = field(default_factory=list)


@dataclass
class MonthlyCostReport:
    month: str
    total_cost: float
    currency: str
    by_category: Dict[str, float]
    by_resource: Dict[str, float]
    generated_at: datetime = field(default_factory=datetime.now)


class CostAnalyzer:
    def __init__(self, currency: str = "CNY"):
        self._currency = currency
        self._costs: List[CostEntry] = []
        self._monthly_reports: Dict[str, MonthlyCostReport] = {}

    def record_cost(
        self,
        resource_type: str,
        resource_name: str,
        units: float,
        unit_price: float,
        metadata: Optional[Dict[str, str]] = None,
    ) -> CostEntry:
        entry = CostEntry(
            resource_type=resource_type,
            resource_name=resource_name,
            amount=units * unit_price,
            currency=self._currency,
            units=units,
            unit_price=unit_price,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )
        self._costs.append(entry)
        return entry

    def record_gpu_cost(
        self,
        gpu_id: int,
        hours: float,
        hourly_rate: float = 25.0,
    ) -> CostEntry:
        return self.record_cost(
            resource_type="GPU",
            resource_name=f"GPU_{gpu_id}",
            units=hours,
            unit_price=hourly_rate,
            metadata={"gpu_id": str(gpu_id), "type": "compute"},
        )

    def record_storage_cost(
        self,
        storage_type: str,
        gb: float,
        price_per_gb: float = 0.15,
    ) -> CostEntry:
        return self.record_cost(
            resource_type="STORAGE",
            resource_name=storage_type,
            units=gb,
            unit_price=price_per_gb,
            metadata={"type": "storage"},
        )

    def record_api_cost(
        self,
        provider: str,
        model: str,
        tokens: int,
        price_per_1k: float = 0.002,
    ) -> CostEntry:
        return self.record_cost(
            resource_type="API",
            resource_name=f"{provider}/{model}",
            units=tokens / 1000.0,
            unit_price=price_per_1k,
            metadata={"provider": provider, "model": model, "tokens": str(tokens)},
        )

    def record_inference_cost(
        self,
        model: str,
        requests: int,
        cost_per_request: float = 0.01,
    ) -> CostEntry:
        return self.record_cost(
            resource_type="INFERENCE",
            resource_name=model,
            units=requests,
            unit_price=cost_per_request,
            metadata={"model": model, "type": "inference"},
        )

    def get_breakdown(
        self,
        resource_type: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> CostBreakdown:
        entries = self._costs
        if resource_type:
            entries = [e for e in entries if e.resource_type == resource_type]
        if since:
            entries = [e for e in entries if e.timestamp >= since]

        total = sum(e.amount for e in entries)
        start = min((e.timestamp for e in entries), default=datetime.now())
        end = max((e.timestamp for e in entries), default=datetime.now())

        return CostBreakdown(
            category=resource_type or "ALL",
            total_amount=round(total, 2),
            currency=self._currency,
            entries_count=len(entries),
            period_start=start,
            period_end=end,
            details=entries,
        )

    def get_daily_cost(self, date: Optional[datetime] = None) -> CostBreakdown:
        target = date or datetime.now()
        day_start = target.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = target.replace(hour=23, minute=59, second=59, microsecond=999999)
        entries = [e for e in self._costs if day_start <= e.timestamp <= day_end]

        total = sum(e.amount for e in entries)
        return CostBreakdown(
            category="DAILY",
            total_amount=round(total, 2),
            currency=self._currency,
            entries_count=len(entries),
            period_start=day_start,
            period_end=day_end,
            details=entries,
        )

    def get_monthly_cost(self, year: int, month: int) -> CostBreakdown:
        month_start = datetime(year, month, 1)
        if month == 12:
            month_end = datetime(year + 1, 1, 1)
        else:
            month_end = datetime(year, month + 1, 1)
        entries = [e for e in self._costs if month_start <= e.timestamp < month_end]

        total = sum(e.amount for e in entries)
        by_cat: Dict[str, float] = defaultdict(float)
        for e in entries:
            by_cat[e.resource_type] += e.amount

        return CostBreakdown(
            category=f"{year}-{month:02d}",
            total_amount=round(total, 2),
            currency=self._currency,
            entries_count=len(entries),
            period_start=month_start,
            period_end=month_end,
            details=entries,
        )

    def generate_monthly_report(self, year: int, month: int) -> MonthlyCostReport:
        breakdown = self.get_monthly_cost(year, month)
        by_resource: Dict[str, float] = defaultdict(float)
        for e in breakdown.details:
            by_resource[e.resource_name] += e.amount

        report = MonthlyCostReport(
            month=f"{year}-{month:02d}",
            total_cost=breakdown.total_amount,
            currency=self._currency,
            by_category=dict(sorted(
                {e.resource_type: sum(a.amount for a in breakdown.details if a.resource_type == e.resource_type)
                 for e in breakdown.details}.items(),
                key=lambda x: x[1],
                reverse=True,
            )),
            by_resource=dict(sorted(by_resource.items(), key=lambda x: x[1], reverse=True)),
        )
        self._monthly_reports[report.month] = report
        return report

    def get_cost_summary(self) -> Dict[str, float]:
        by_category: Dict[str, float] = defaultdict(float)
        for e in self._costs:
            by_category[e.resource_type] += e.amount
        return {k: round(v, 2) for k, v in by_category.items()}

    def get_total_cost(self) -> float:
        return round(sum(e.amount for e in self._costs), 2)

    def clear_history(self):
        self._costs.clear()
        self._monthly_reports.clear()
