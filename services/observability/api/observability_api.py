from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional

from ...service import ObservabilityService

router = APIRouter(prefix="/api/v1/observability", tags=["observability"])

service = ObservabilityService()


class AlertRequest(BaseModel):
    metric_name: str
    value: float


class IncidentRequest(BaseModel):
    incident_id: str
    title: str
    description: str
    affected_service: str
    severity: str = "HIGH"
    symptoms: Optional[List[str]] = None


class SLODefineRequest(BaseModel):
    slo_id: str
    name: str
    service: str
    slo_type: str
    target_value: float
    window_days: int = 30


class GPURegisterRequest(BaseModel):
    gpu_id: int
    name: str = "GPU"
    memory_total_mb: float = 24576.0


class GPUUpdateRequest(BaseModel):
    gpu_id: int
    utilization_pct: float
    memory_used_mb: float
    temperature_c: float = 45.0
    power_draw_w: float = 0.0
    oom_events: int = 0


class AIModelUpdateRequest(BaseModel):
    model_name: str
    latency_ms: float
    error_rate: float
    requests_per_minute: float


class StressTestRequest(BaseModel):
    scenario: str


@router.get("/status")
async def get_system_status():
    return service.get_system_status()


@router.get("/trace/{trace_id}")
async def get_trace(trace_id: str):
    result = service.get_trace(trace_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    return result


@router.get("/traces")
async def list_traces(limit: int = 20):
    traces = service.tracing.get_all_traces()
    return {
        "traces": [
            {
                "trace_id": t.trace_id,
                "service": t.service,
                "span_count": len(t.spans),
                "has_errors": t.has_errors,
            }
            for t in traces[:limit]
        ]
    }


@router.get("/ai")
async def get_ai_status():
    return service.get_ai_status()


@router.post("/ai/models/register")
async def register_ai_model(request: AIModelUpdateRequest):
    service.ai_monitor.register_model(request.model_name, "LLM")
    return {"status": "registered", "model": request.model_name}


@router.post("/ai/models/update")
async def update_ai_model(request: AIModelUpdateRequest):
    health = service.ai_monitor.update_health(
        request.model_name,
        request.latency_ms,
        request.error_rate,
        request.requests_per_minute,
    )
    return {
        "model": health.model_name,
        "status": health.status,
        "latency_ms": health.latency_ms,
        "error_rate": health.error_rate,
    }


@router.get("/gpu")
async def get_gpu_status():
    cluster = service.gpu_monitor.get_cluster_status()
    return cluster.__dict__


@router.post("/gpu/register")
async def register_gpu(request: GPURegisterRequest):
    service.gpu_monitor.register_gpu(request.gpu_id, request.name, request.memory_total_mb)
    return {"status": "registered", "gpu_id": request.gpu_id}


@router.post("/gpu/update")
async def update_gpu(request: GPUUpdateRequest):
    stats = service.gpu_monitor.update_stats(
        request.gpu_id,
        request.utilization_pct,
        request.memory_used_mb,
        request.temperature_c,
        request.power_draw_w,
        request.oom_events,
    )
    return stats.to_dict()


@router.get("/cost")
async def get_cost_report():
    return service.get_cost_report()


@router.get("/exposure")
async def get_exposure_report():
    return service.get_exposure_report()


@router.post("/stress")
async def run_stress_test(request: StressTestRequest):
    return service.run_stress_test(request.scenario)


@router.get("/alerts")
async def get_alerts(severity: Optional[str] = None):
    return {"alerts": service.get_alerts(severity)}


@router.post("/alerts/evaluate")
async def evaluate_alert(request: AlertRequest):
    triggered = service.alert_engine.evaluate_metric(request.metric_name, request.value)
    return {
        "triggered": len(triggered) > 0,
        "alerts": [
            {
                "alert_id": a.alert_id,
                "severity": a.severity,
                "message": a.message,
            }
            for a in triggered
        ],
    }


@router.get("/anomalies")
async def get_anomalies(limit: int = 20):
    return {"anomalies": service.get_anomalies(limit)}


@router.post("/rca")
async def perform_rca(request: IncidentRequest):
    return service.perform_rca(
        incident_id=request.incident_id,
        title=request.title,
        description=request.description,
        affected_service=request.affected_service,
        severity=request.severity,
        symptoms=request.symptoms,
    )


@router.get("/dashboard")
async def get_dashboard():
    return service.get_dashboard_snapshot()


@router.get("/slo")
async def get_slo_status():
    return {"slos": service.get_slo_status()}


@router.post("/slo/define")
async def define_slo(request: SLODefineRequest):
    slo = service.slo_manager.define_slo(
        request.slo_id,
        request.name,
        request.service,
        request.slo_type,
        request.target_value,
        request.window_days,
    )
    return {"status": "defined", "slo_id": slo.slo_id}


@router.get("/sla")
async def get_sla_status():
    return service.get_sla_status()


@router.get("/metrics")
async def get_metrics():
    return service.metrics.get_metrics()


@router.get("/logs")
async def get_logs(limit: int = 100):
    logs = service.log_manager.get_all_logs(limit)
    return {
        "logs": [
            {
                "timestamp": l.timestamp.isoformat(),
                "level": l.level,
                "category": l.category,
                "service": l.service,
                "message": l.message,
                "trace_id": l.trace_id,
            }
            for l in logs
        ]
    }
