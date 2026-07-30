from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict


@dataclass
class InferenceMetrics:
    model_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    timeout_requests: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    total_tokens_used: int
    avg_tokens_per_request: float
    success_rate: float
    period_start: datetime
    period_end: datetime

    @property
    def is_healthy(self) -> bool:
        return self.success_rate >= 0.95 and self.p95_latency_ms < 1000


@dataclass
class InferenceRequest:
    request_id: str
    model_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    latency_ms: float = 0
    tokens_used: int = 0
    status: str = "PENDING"
    error: Optional[str] = None


class InferenceMonitor:
    def __init__(self):
        self._requests: List[InferenceRequest] = []
        self._model_metrics: Dict[str, List[InferenceRequest]] = defaultdict(list)
        self._models: List[str] = []

    def register_model(self, model_name: str):
        if model_name not in self._models:
            self._models.append(model_name)

    def start_request(self, request_id: str, model_name: str) -> InferenceRequest:
        req = InferenceRequest(
            request_id=request_id,
            model_name=model_name,
            start_time=datetime.now(),
        )
        self._requests.append(req)
        self._model_metrics[model_name].append(req)
        return req

    def complete_request(
        self,
        request_id: str,
        tokens_used: int = 0,
        success: bool = True,
        timeout: bool = False,
        error: Optional[str] = None,
    ):
        req = self._find_request(request_id)
        if req:
            import time
            time.sleep(0.001)
            req.end_time = datetime.now()
            req.latency_ms = (req.end_time - req.start_time).total_seconds() * 1000
            if req.latency_ms == 0:
                req.latency_ms = 0.1
            req.tokens_used = tokens_used
            if timeout:
                req.status = "TIMEOUT"
                req.error = error or "Request timed out"
            elif success:
                req.status = "SUCCESS"
            else:
                req.status = "FAILED"
                req.error = error or "Request failed"

    def _find_request(self, request_id: str) -> Optional[InferenceRequest]:
        for req in self._requests:
            if req.request_id == request_id:
                return req
        return None

    def get_metrics(
        self,
        model_name: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> InferenceMetrics:
        requests = self._requests
        if model_name:
            requests = [r for r in requests if r.model_name == model_name]
        if since:
            requests = [r for r in requests if r.start_time >= since]

        completed = [r for r in requests if r.end_time]
        successful = [r for r in completed if r.status == "SUCCESS"]
        failed = [r for r in completed if r.status == "FAILED"]
        timeout = [r for r in completed if r.status == "TIMEOUT"]

        latencies = sorted([r.latency_ms for r in completed if r.latency_ms > 0])
        total_tokens = sum(r.tokens_used for r in completed)

        n = len(latencies)
        p50 = latencies[int(n * 0.50)] if n > 0 else 0
        p95 = latencies[int(n * 0.95)] if n > 0 else 0
        p99 = latencies[int(n * 0.99)] if n > 0 else 0
        avg = sum(latencies) / n if n > 0 else 0

        start = min((r.start_time for r in requests), default=datetime.now())
        end = max((r.end_time or r.start_time for r in requests), default=datetime.now())

        total = len(completed)
        success_rate = len(successful) / total if total > 0 else 0

        return InferenceMetrics(
            model_name=model_name or "ALL",
            total_requests=total,
            successful_requests=len(successful),
            failed_requests=len(failed),
            timeout_requests=len(timeout),
            avg_latency_ms=round(avg, 2),
            p50_latency_ms=round(p50, 2),
            p95_latency_ms=round(p95, 2),
            p99_latency_ms=round(p99, 2),
            total_tokens_used=total_tokens,
            avg_tokens_per_request=round(total_tokens / total, 1) if total > 0 else 0,
            success_rate=round(success_rate, 4),
            period_start=start,
            period_end=end,
        )

    def get_all_model_metrics(self) -> Dict[str, InferenceMetrics]:
        return {
            model: self.get_metrics(model_name=model)
            for model in self._models
        }

    def get_recent_requests(self, limit: int = 20) -> List[InferenceRequest]:
        return sorted(self._requests, key=lambda r: r.start_time, reverse=True)[:limit]

    def get_request(self, request_id: str) -> Optional[InferenceRequest]:
        return self._find_request(request_id)

    def clear_history(self):
        self._requests.clear()
        self._model_metrics.clear()
