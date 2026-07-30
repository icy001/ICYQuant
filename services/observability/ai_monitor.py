from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime


class AIModelType(Enum):
    LLM = "LLM"
    EMBEDDING = "EMBEDDING"
    RL_MODEL = "RL_MODEL"
    PREDICTION = "PREDICTION"
    CLASSIFIER = "CLASSIFIER"


class AIHealthStatus(Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


@dataclass
class ModelHealth:
    model_name: str
    model_type: str
    status: str
    latency_ms: float
    error_rate: float
    requests_per_minute: float
    last_check: datetime
    message: str = ""


@dataclass
class AIServiceStatus:
    service_name: str
    models: List[ModelHealth] = field(default_factory=list)
    overall_status: str = AIHealthStatus.UNKNOWN.value
    checked_at: datetime = field(default_factory=datetime.now)

    def get_model_status(self, model_name: str) -> Optional[ModelHealth]:
        for m in self.models:
            if m.model_name == model_name:
                return m
        return None


class AIMonitor:
    def __init__(self):
        self._models: Dict[str, ModelHealth] = {}
        self._history: List[AIServiceStatus] = []
        self._thresholds = {
            "max_latency_ms": 500.0,
            "max_error_rate": 0.05,
            "min_rpm": 0.0,
        }

    def register_model(
        self,
        model_name: str,
        model_type: str,
    ):
        if model_name not in self._models:
            self._models[model_name] = ModelHealth(
                model_name=model_name,
                model_type=model_type,
                status=AIHealthStatus.UNKNOWN.value,
                latency_ms=0,
                error_rate=0,
                requests_per_minute=0,
                last_check=datetime.now(),
            )

    def update_health(
        self,
        model_name: str,
        latency_ms: float,
        error_rate: float,
        requests_per_minute: float,
    ) -> ModelHealth:
        model = self._models.get(model_name)
        if not model:
            model = ModelHealth(
                model_name=model_name,
                model_type=AIModelType.LLM.value,
                status=AIHealthStatus.UNKNOWN.value,
                latency_ms=latency_ms,
                error_rate=error_rate,
                requests_per_minute=requests_per_minute,
                last_check=datetime.now(),
            )
            self._models[model_name] = model

        model.latency_ms = latency_ms
        model.error_rate = error_rate
        model.requests_per_minute = requests_per_minute
        model.last_check = datetime.now()
        model.status = self._evaluate_status(latency_ms, error_rate)

        return model

    def _evaluate_status(self, latency_ms: float, error_rate: float) -> str:
        if error_rate > self._thresholds["max_error_rate"]:
            return AIHealthStatus.UNHEALTHY.value
        if latency_ms > self._thresholds["max_latency_ms"]:
            return AIHealthStatus.DEGRADED.value
        return AIHealthStatus.HEALTHY.value

    def get_model_health(self, model_name: str) -> Optional[ModelHealth]:
        return self._models.get(model_name)

    def get_all_models(self) -> List[ModelHealth]:
        return list(self._models.values())

    def get_service_status(self) -> AIServiceStatus:
        models = list(self._models.values())
        if not models:
            return AIServiceStatus(
                service_name="ai",
                overall_status=AIHealthStatus.UNKNOWN.value,
            )

        if any(m.status == AIHealthStatus.UNHEALTHY.value for m in models):
            overall = AIHealthStatus.UNHEALTHY.value
        elif any(m.status == AIHealthStatus.DEGRADED.value for m in models):
            overall = AIHealthStatus.DEGRADED.value
        elif all(m.status == AIHealthStatus.HEALTHY.value for m in models):
            overall = AIHealthStatus.HEALTHY.value
        else:
            overall = AIHealthStatus.UNKNOWN.value

        status = AIServiceStatus(
            service_name="ai",
            models=models,
            overall_status=overall,
        )
        self._history.append(status)
        return status

    def set_thresholds(self, max_latency_ms: float = None, max_error_rate: float = None):
        if max_latency_ms is not None:
            self._thresholds["max_latency_ms"] = max_latency_ms
        if max_error_rate is not None:
            self._thresholds["max_error_rate"] = max_error_rate

    def check_model(self, model_name: str) -> Dict:
        model = self._models.get(model_name)
        if not model:
            return {"model": model_name, "status": "NOT_FOUND", "message": "Model not registered"}
        return {
            "model": model.model_name,
            "type": model.model_type,
            "status": model.status,
            "latency_ms": model.latency_ms,
            "error_rate": model.error_rate,
            "rpm": model.requests_per_minute,
            "healthy": model.status == AIHealthStatus.HEALTHY.value,
        }
