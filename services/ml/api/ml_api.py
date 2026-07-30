"""ML Platform REST API.

Endpoints:
    POST   /api/v1/ml/experiment           - Create experiment
    GET    /api/v1/ml/experiment/{id}       - Get experiment
    GET    /api/v1/ml/experiments           - List experiments
    POST   /api/v1/ml/experiment/{id}/run   - Start a run
    POST   /api/v1/ml/experiment/{id}/log   - Log metrics/params
    POST   /api/v1/ml/model/register        - Register model
    GET    /api/v1/ml/model/{name}          - Get model info
    GET    /api/v1/ml/models                - List all models
    POST   /api/v1/ml/model/{name}/promote  - Promote model
    POST   /api/v1/ml/artifact              - Save artifact
    GET    /api/v1/ml/artifact/{id}         - Get artifact
    GET    /api/v1/ml/experiment/{id}/artifacts - List artifacts
    GET    /api/v1/ml/status                - Platform status
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from services.ml.service import MLService
from services.ml.metadata import ModelStage, ModelFramework
from services.ml.artifact import ArtifactType
from services.ml.experiment import ExperimentStatus

router = APIRouter(prefix="/api/v1/ml", tags=["ML Platform"])

_ml_service = MLService()


# ============================================================
#  Experiment Endpoints
# ============================================================

@router.post("/experiment", summary="Create a new ML experiment")
async def create_experiment(
    name: str = Query(..., description="Experiment name"),
    framework: str = Query("LightGBM", description="ML framework"),
    description: str = Query("", description="Experiment description"),
    dataset: str = Query("", description="Training dataset identifier"),
    features: int = Query(0, description="Number of features"),
) -> Dict[str, Any]:
    """Create a new experiment.

    Request example::

        POST /api/v1/ml/experiment?name=alpha_v18&framework=LightGBM
    """
    exp = _ml_service.create_experiment(
        name=name,
        framework=framework,
        description=description,
        dataset=dataset,
        features=features,
    )
    return exp.to_dict()


@router.get("/experiment/{experiment_id}", summary="Get experiment by ID")
async def get_experiment(experiment_id: str) -> Dict[str, Any]:
    """Get experiment details."""
    exp = _ml_service.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found")
    return exp.to_dict()


@router.get("/experiments", summary="List all experiments")
async def list_experiments(
    status: Optional[str] = Query(None, description="Filter by status"),
) -> List[Dict[str, Any]]:
    """List all experiments, optionally filtered by status."""
    exp_status = ExperimentStatus(status) if status else None
    exps = _ml_service.list_experiments(status=exp_status)
    return [e.to_dict() for e in exps]


@router.post("/experiments/search", summary="Search experiments")
async def search_experiments(
    name_contains: str = Query("", description="Name substring to match"),
    framework: str = Query("", description="Framework filter"),
) -> List[Dict[str, Any]]:
    """Search experiments by name or framework."""
    exps = _ml_service.search_experiments(name_contains=name_contains, framework=framework)
    return [e.to_dict() for e in exps]


# ============================================================
#  Run Endpoints (within Experiment)
# ============================================================

@router.post("/experiment/{experiment_id}/run", summary="Start a new run")
async def start_run(experiment_id: str) -> Dict[str, Any]:
    """Start a new run within an experiment."""
    run = _ml_service.start_run(experiment_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found")
    return run.to_dict()


@router.post("/experiment/{experiment_id}/run/{run_id}/finish", summary="Finish a run")
async def finish_run(
    experiment_id: str,
    run_id: str,
    status: str = Query("Completed", description="Run final status"),
) -> Dict[str, Any]:
    """Finish a run."""
    run_status = ExperimentStatus(status)
    ok = _ml_service.finish_run(experiment_id, run_id, run_status)
    if not ok:
        raise HTTPException(status_code=404, detail="Experiment or run not found")
    run = _ml_service.tracker.get_run(experiment_id, run_id)
    return (run.to_dict() if run else {"status": status})  # type: ignore[union-attr]


@router.post("/experiment/{experiment_id}/log", summary="Log metrics and parameters")
async def log_metrics(
    experiment_id: str,
    run_id: str = Query(..., description="Run ID"),
    sharpe: Optional[float] = Query(None, description="Sharpe ratio"),
    accuracy: Optional[float] = Query(None, description="Model accuracy"),
    learning_rate: Optional[float] = Query(None, description="Learning rate"),
    max_depth: Optional[int] = Query(None, description="Max tree depth"),
) -> Dict[str, Any]:
    """Log metrics and parameters for a run.

    Request example::

        POST /api/v1/ml/experiment/{id}/log?run_id=xxx&sharpe=2.03&accuracy=0.742&learning_rate=0.05
    """
    metrics: Dict[str, float] = {}
    params: Dict[str, Any] = {}

    if sharpe is not None:
        metrics["sharpe"] = sharpe
    if accuracy is not None:
        metrics["accuracy"] = accuracy
    if learning_rate is not None:
        params["learning_rate"] = learning_rate
    if max_depth is not None:
        params["max_depth"] = max_depth

    if metrics:
        _ml_service.log_metrics(experiment_id, run_id, metrics)
    if params:
        _ml_service.log_params(experiment_id, run_id, params)
    return {"experiment_id": experiment_id, "run_id": run_id, "logged": True}


# ============================================================
#  Model Registry Endpoints
# ============================================================

@router.post("/model/register", summary="Register a new model version")
async def register_model(
    model: str = Query(..., description="Model name"),
    version: str = Query(..., description="Version string (e.g. v4)"),
    experiment_id: str = Query("", description="Parent experiment ID"),
    framework: str = Query("LightGBM", description="ML framework"),
    dataset: str = Query("", description="Training dataset"),
    author: str = Query("", description="Model author"),
    description: str = Query("", description="Model description"),
) -> Dict[str, Any]:
    """Register a model version.

    Request example::

        POST /api/v1/ml/model/register?model=alpha_model&version=v4&framework=LightGBM
    """
    try:
        entry = _ml_service.register_model(
            model_name=model,
            version=version,
            experiment_id=experiment_id,
            author=author or "api_user",
            framework=ModelFramework(framework),
            dataset=dataset,
            description=description,
        )
        return entry.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/model/{name}", summary="Get model registry info")
async def get_model(name: str) -> Dict[str, Any]:
    """Get information about a registered model.

    Returns the latest version and current stage.

    Example response::

        {"model": "alpha_model", "latest": "v4", "stage": "Production"}
    """
    entry = _ml_service.get_model(name)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Model '{name}' not found")
    prod = _ml_service.registry.get_production(name)
    result: Dict[str, Any] = {
        "model": name,
        "latest": entry.latest_version,
    }
    if prod:
        result["stage"] = prod.stage.value
    else:
        result["stage"] = entry.versions[0].stage.value if entry.versions else "Unknown"
    result["versions"] = [v.to_dict() for v in entry.versions]
    return result


@router.get("/models", summary="List all registered models")
async def list_models() -> List[Dict[str, Any]]:
    """List all registered models."""
    return _ml_service.list_models()


@router.post("/model/{name}/promote", summary="Promote a model version")
async def promote_model(
    name: str,
    version: str = Query(..., description="Version to promote"),
    stage: str = Query(..., description="Target stage (Testing/Staging/Production/Archived)"),
) -> Dict[str, Any]:
    """Promote a model to a new lifecycle stage."""
    mv = _ml_service.registry.get_version(name, version)
    if not mv:
        raise HTTPException(status_code=404, detail=f"Model '{name}' version '{version}' not found")
    try:
        target = ModelStage(stage)
        _ml_service.promote_model(name, version, target)
        return {"model": name, "version": version, "stage": stage, "promoted": True}
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
#  Artifact Endpoints
# ============================================================

@router.get("/experiment/{experiment_id}/artifacts", summary="List experiment artifacts")
async def list_artifacts(experiment_id: str) -> List[Dict[str, Any]]:
    """List all artifacts for an experiment."""
    return _ml_service.list_experiment_artifacts(experiment_id)


@router.get("/artifact/{artifact_id}", summary="Get artifact metadata")
async def get_artifact(artifact_id: str) -> Dict[str, Any]:
    """Get artifact metadata."""
    art = _ml_service.get_artifact(artifact_id)
    if not art:
        raise HTTPException(status_code=404, detail=f"Artifact '{artifact_id}' not found")
    return art.to_dict()


# ============================================================
#  Platform Status
# ============================================================

@router.get("/status", summary="Get ML platform status")
async def get_status() -> Dict[str, Any]:
    """Get overall ML platform status summary."""
    return _ml_service.get_status()
