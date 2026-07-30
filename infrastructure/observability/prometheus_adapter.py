from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class PrometheusMetric:
    name: str
    value: float
    labels: Dict[str, str]
    type: str


class PrometheusAdapter:
    def __init__(self, port: int = 9090):
        self.port = port
        self._metrics: Dict[str, PrometheusMetric] = {}

    def register_metric(
        self,
        name: str,
        value: float,
        metric_type: str = "gauge",
        labels: Optional[Dict[str, str]] = None,
    ):
        self._metrics[name] = PrometheusMetric(
            name=name,
            value=value,
            labels=labels or {},
            type=metric_type,
        )

    def update_metric(self, name: str, value: float):
        if name in self._metrics:
            self._metrics[name].value = value

    def get_metric(self, name: str) -> Optional[PrometheusMetric]:
        return self._metrics.get(name)

    def get_all_metrics(self) -> List[PrometheusMetric]:
        return list(self._metrics.values())

    def format_prometheus(self) -> str:
        lines = []
        for m in self._metrics.values():
            lines.append(f"# HELP {m.name}")
            lines.append(f"# TYPE {m.name} {m.type}")
            label_str = ",".join(f'{k}="{v}"' for k, v in m.labels.items())
            lines.append(f'{m.name}{{{label_str}}} {m.value}')
        return "\n".join(lines)

    def scrape(self) -> str:
        return self.format_prometheus()

    @property
    def endpoint(self) -> str:
        return f"http://localhost:{self.port}/metrics"
