from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict
import statistics


@dataclass
class AnomalyDetectionResult:
    metric_name: str
    is_anomaly: bool
    anomaly_type: str
    severity: str
    current_value: float
    expected_range: tuple
    z_score: float
    confidence: float
    timestamp: datetime
    details: Dict[str, float] = field(default_factory=dict)


class AnomalyDetector:
    def __init__(self, sensitivity: float = 2.0, min_samples: int = 5):
        self._sensitivity = sensitivity
        self._min_samples = min_samples
        self._history: Dict[str, List[float]] = defaultdict(list)
        self._results: List[AnomalyDetectionResult] = []

    def add_data_point(self, metric_name: str, value: float):
        self._history[metric_name].append(value)

    def detect(
        self,
        metric_name: str,
        value: float,
        window: Optional[int] = None,
    ) -> AnomalyDetectionResult:
        history = self._history.get(metric_name, [])
        if len(history) < self._min_samples:
            result = AnomalyDetectionResult(
                metric_name=metric_name,
                is_anomaly=False,
                anomaly_type="INSUFFICIENT_DATA",
                severity="UNKNOWN",
                current_value=value,
                expected_range=(value, value),
                z_score=0.0,
                confidence=0.0,
                timestamp=datetime.now(),
            )
            self._results.append(result)
            return result

        data = history[-window:] if window else history
        mean = statistics.mean(data)
        stdev = statistics.stdev(data) if len(data) > 1 else 0.0

        if stdev == 0:
            z_score = 0.0
        else:
            z_score = abs(value - mean) / stdev

        lower = mean - self._sensitivity * stdev
        upper = mean + self._sensitivity * stdev
        is_anomaly = z_score > self._sensitivity

        if is_anomaly:
            if z_score > 3:
                severity = "CRITICAL"
            elif z_score > 2.5:
                severity = "HIGH"
            elif z_score > 2.0:
                severity = "MEDIUM"
            else:
                severity = "LOW"

            if value > upper:
                anomaly_type = "SPIKE"
            else:
                anomaly_type = "DROP"

            confidence = min(1.0, z_score / (self._sensitivity * 2))
        else:
            severity = "NORMAL"
            anomaly_type = "NONE"
            confidence = 0.0

        result = AnomalyDetectionResult(
            metric_name=metric_name,
            is_anomaly=is_anomaly,
            anomaly_type=anomaly_type,
            severity=severity,
            current_value=value,
            expected_range=(round(lower, 4), round(upper, 4)),
            z_score=round(z_score, 4),
            confidence=round(confidence, 4),
            timestamp=datetime.now(),
            details={
                "mean": round(mean, 4),
                "stdev": round(stdev, 4),
                "lower_bound": round(lower, 4),
                "upper_bound": round(upper, 4),
                "sample_count": len(data),
            },
        )
        self._results.append(result)
        return result

    def detect_latency_anomaly(
        self,
        service: str,
        latency_ms: float,
    ) -> AnomalyDetectionResult:
        metric_name = f"latency.{service}"
        return self.detect(metric_name, latency_ms)

    def detect_memory_anomaly(
        self,
        service: str,
        memory_used_pct: float,
    ) -> AnomalyDetectionResult:
        metric_name = f"memory.{service}"
        return self.detect(metric_name, memory_used_pct)

    def detect_volume_anomaly(
        self,
        service: str,
        requests_per_sec: float,
    ) -> AnomalyDetectionResult:
        metric_name = f"volume.{service}"
        return self.detect(metric_name, requests_per_sec)

    def get_recent_anomalies(
        self,
        limit: int = 20,
        severity: Optional[str] = None,
    ) -> List[AnomalyDetectionResult]:
        anomalies = [r for r in self._results if r.is_anomaly]
        if severity:
            anomalies = [r for r in anomalies if r.severity == severity]
        return sorted(anomalies, key=lambda r: r.timestamp, reverse=True)[:limit]

    def get_all_results(self, limit: int = 50) -> List[AnomalyDetectionResult]:
        return sorted(self._results, key=lambda r: r.timestamp, reverse=True)[:limit]

    def clear_history(self):
        self._history.clear()
        self._results.clear()
