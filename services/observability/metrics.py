from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime
from collections import defaultdict


class MetricType(Enum):
    COUNTER = "COUNTER"
    GAUGE = "GAUGE"
    HISTOGRAM = "HISTOGRAM"
    TIMER = "TIMER"


@dataclass
class MetricData:
    name: str
    value: float
    type: str
    service: str
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class Counter:
    def __init__(self, name: str, service: str = ""):
        self.name = name
        self.service = service
        self._value: float = 0
        self._history: List[MetricData] = []

    def increment(self, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        self._value += value
        self._history.append(MetricData(
            name=self.name,
            value=self._value,
            type=MetricType.COUNTER.value,
            service=self.service,
            labels=labels or {},
        ))

    def get(self) -> float:
        return self._value

    def snapshot(self) -> MetricData:
        return MetricData(
            name=self.name,
            value=self._value,
            type=MetricType.COUNTER.value,
            service=self.service,
        )


class Gauge:
    def __init__(self, name: str, service: str = ""):
        self.name = name
        self.service = service
        self._value: float = 0
        self._history: List[MetricData] = []

    def set(self, value: float, labels: Optional[Dict[str, str]] = None):
        self._value = value
        self._history.append(MetricData(
            name=self.name,
            value=self._value,
            type=MetricType.GAUGE.value,
            service=self.service,
            labels=labels or {},
        ))

    def increment(self, value: float = 1.0):
        self._value += value

    def decrement(self, value: float = 1.0):
        self._value -= value

    def get(self) -> float:
        return self._value

    def snapshot(self) -> MetricData:
        return MetricData(
            name=self.name,
            value=self._value,
            type=MetricType.GAUGE.value,
            service=self.service,
        )


class Histogram:
    def __init__(self, name: str, service: str = "", buckets: Optional[List[float]] = None):
        self.name = name
        self.service = service
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 5.0, 10.0]
        self._count: int = 0
        self._sum: float = 0
        self._values: List[float] = []
        self._bucket_counts: Dict[float, int] = defaultdict(int)

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None):
        self._count += 1
        self._sum += value
        self._values.append(value)
        for bucket in self.buckets:
            if value <= bucket:
                self._bucket_counts[bucket] += 1

    @property
    def count(self) -> int:
        return self._count

    @property
    def mean(self) -> float:
        return self._sum / self._count if self._count > 0 else 0

    @property
    def p50(self) -> float:
        return self._percentile(0.50)

    @property
    def p95(self) -> float:
        return self._percentile(0.95)

    @property
    def p99(self) -> float:
        return self._percentile(0.99)

    def _percentile(self, pct: float) -> float:
        if not self._values:
            return 0.0
        sorted_vals = sorted(self._values)
        idx = int(len(sorted_vals) * pct)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]

    def snapshot(self) -> Dict:
        return {
            "name": self.name,
            "count": self._count,
            "sum": self._sum,
            "mean": self.mean,
            "p50": self.p50,
            "p95": self.p95,
            "p99": self.p99,
        }


class MetricsRegistry:
    def __init__(self):
        self._counters: Dict[str, Counter] = {}
        self._gauges: Dict[str, Gauge] = {}
        self._histograms: Dict[str, Histogram] = {}

    def counter(self, name: str, service: str = "") -> Counter:
        if name not in self._counters:
            self._counters[name] = Counter(name, service)
        return self._counters[name]

    def gauge(self, name: str, service: str = "") -> Gauge:
        if name not in self._gauges:
            self._gauges[name] = Gauge(name, service)
        return self._gauges[name]

    def histogram(self, name: str, service: str = "", buckets: Optional[List[float]] = None) -> Histogram:
        if name not in self._histograms:
            self._histograms[name] = Histogram(name, service, buckets)
        return self._histograms[name]

    def get_counter(self, name: str) -> Optional[Counter]:
        return self._counters.get(name)

    def get_gauge(self, name: str) -> Optional[Gauge]:
        return self._gauges.get(name)

    def get_histogram(self, name: str) -> Optional[Histogram]:
        return self._histograms.get(name)

    def get_all(self) -> Dict:
        return {
            "counters": {k: v.snapshot() for k, v in self._counters.items()},
            "gauges": {k: v.snapshot() for k, v in self._gauges.items()},
            "histograms": {k: v.snapshot() for k, v in self._histograms.items()},
        }

    def get_counter_names(self) -> List[str]:
        return list(self._counters.keys())

    def get_gauge_names(self) -> List[str]:
        return list(self._gauges.keys())

    def get_histogram_names(self) -> List[str]:
        return list(self._histograms.keys())


class MetricsCollector:
    def __init__(self):
        self._registry = MetricsRegistry()
        self._collected: List[MetricData] = []

    @property
    def registry(self) -> MetricsRegistry:
        return self._registry

    def collect(self, metric: MetricData):
        self._collected.append(metric)

    def counter(self, name: str, service: str = "") -> Counter:
        return self._registry.counter(name, service)

    def gauge(self, name: str, service: str = "") -> Gauge:
        return self._registry.gauge(name, service)

    def histogram(self, name: str, service: str = "", buckets: Optional[List[float]] = None) -> Histogram:
        return self._registry.histogram(name, service, buckets)

    def get_metrics(self) -> Dict:
        return self._registry.get_all()

    def get_all_collected(self) -> List[MetricData]:
        return list(self._collected)

    def get_collected_by_service(self, service: str) -> List[MetricData]:
        return [m for m in self._collected if m.service == service]

    def snapshot(self) -> Dict:
        return self._registry.get_all()

    def all(self) -> List[MetricData]:
        return self.get_all_collected()

    def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        counter = self._registry.counter(name)
        counter.increment(value, labels)

    def get(self, name: str) -> float:
        counter = self._registry.get_counter(name)
        if counter:
            return counter.get()
        gauge = self._registry.get_gauge(name)
        if gauge:
            return gauge.get()
        return 0.0

    def clear(self):
        self._collected.clear()
