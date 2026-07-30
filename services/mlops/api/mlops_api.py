"""
MLOps REST API Controller.

Endpoints:
    POST   /api/v1/mlops/train          — Trigger training
    GET    /api/v1/mlops/drift           — Get drift status
    GET    /api/v1/mlops/champion        — Get current champion
    POST   /api/v1/mlops/deploy          — Deploy model
    POST   /api/v1/mlops/approve         — Approve a deployment
    GET    /api/v1/mlops/lifecycle/{model} — Get model lifecycle
    GET    /api/v1/mlops/health           — Platform health
    GET    /api/v1/mlops/pipelines        — List pipeline runs
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MLOpsAPI:
    """REST API controller for MLOps operations.

    Wraps the MLOpsService and exposes all endpoints.
    """

    mlops_service: Any = None  # MLOpsService instance

    def __post_init__(self):
        self._request_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # POST /api/v1/mlops/train
    # ------------------------------------------------------------------

    def train(self, pipeline_name: str = "daily_alpha", model_name: str = "") -> Dict[str, Any]:
        """Trigger a training job.

        Args:
            pipeline_name: Pipeline identifier.
            model_name: Optional target model name.

        Returns:
            Training job info.
        """
        if not self.mlops_service:
            return {"status": "error", "message": "MLOps service not configured"}

        target = model_name or pipeline_name
        job = self.mlops_service.trainer.train(model_name=target)
        self._log("train", {"pipeline": pipeline_name, "model": target})

        return {
            "status": "accepted",
            "job_id": job.job_id,
            "model_name": target,
            "pipeline": pipeline_name,
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------
    # GET /api/v1/mlops/drift
    # ------------------------------------------------------------------

    def get_drift(self, model_name: str = "") -> Dict[str, Any]:
        """Get drift status for a model.

        Returns:
            Drift status with feature_drift and model_drift flags.
        """
        if not self.mlops_service:
            return {"status": "error", "message": "MLOps service not configured"}

        if not model_name:
            return {"status": "error", "message": "model_name required"}

        report = self.mlops_service.drift_detector.get_latest_report(model_name)
        if not report:
            return {
                "model_name": model_name,
                "feature_drift": False,
                "model_drift": False,
                "status": "no_data",
            }

        return {
            "model_name": model_name,
            "feature_drift": report.any_data_drift,
            "model_drift": report.any_model_drift,
            "data_drift_severity": report.data_drift_severity.value,
            "model_drift_severity": report.model_drift_severity.value,
            "requires_retraining": report.requires_retraining,
            "summary": report.summary,
            "checked_at": report.generated_at,
        }

    # ------------------------------------------------------------------
    # GET /api/v1/mlops/champion
    # ------------------------------------------------------------------

    def get_champion(self) -> Dict[str, Any]:
        """Get current champion model info.

        Returns:
            Champion model details.
        """
        if not self.mlops_service:
            return {"status": "error", "message": "MLOps service not configured"}

        champion = self.mlops_service.champion_challenger.get_champion()
        if not champion:
            return {"model": None, "status": "no_champion"}

        return {
            "model": champion.model_name,
            "version": champion.model_version,
            "status": "Champion",
            "deployed_at": champion.deployed_at,
            "metrics": champion.metrics_snapshot,
        }

    # ------------------------------------------------------------------
    # POST /api/v1/mlops/deploy
    # ------------------------------------------------------------------

    def deploy(
        self,
        model_name: str = "",
        model_version: str = "",
        strategy: str = "canary",
    ) -> Dict[str, Any]:
        """Deploy a model to production.

        Args:
            model_name: Model to deploy.
            model_version: Version to deploy.
            strategy: Deployment strategy (canary, direct, blue_green, shadow).

        Returns:
            Deployment job info.
        """
        if not self.mlops_service:
            return {"status": "error", "message": "MLOps service not configured"}

        if not model_name or not model_version:
            return {"status": "error", "message": "model_name and model_version required"}

        from services.mlops.deployment import DeploymentStrategy
        strategy_map = {
            "canary": DeploymentStrategy.CANARY,
            "direct": DeploymentStrategy.DIRECT,
            "blue_green": DeploymentStrategy.BLUE_GREEN,
            "shadow": DeploymentStrategy.SHADOW,
        }
        dep_strategy = strategy_map.get(strategy, DeploymentStrategy.CANARY)

        job = self.mlops_service.deployer.deploy(
            model_name=model_name,
            model_version=model_version,
            strategy=dep_strategy,
        )

        return {
            "status": "accepted",
            "job_id": job.job_id,
            "model_name": model_name,
            "model_version": model_version,
            "strategy": strategy,
            "deployment_status": job.status.value,
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------
    # POST /api/v1/mlops/approve
    # ------------------------------------------------------------------

    def approve(
        self, request_id: str = "", approver: str = "admin"
    ) -> Dict[str, Any]:
        """Approve a pending deployment/promotion request.

        Args:
            request_id: Approval request ID.
            approver: Username of the approver.

        Returns:
            Approval result.
        """
        if not self.mlops_service:
            return {"status": "error", "message": "MLOps service not configured"}

        if not request_id:
            return {"status": "error", "message": "request_id required"}

        request = self.mlops_service.approval.get_request(request_id)
        if not request:
            return {"status": "error", "message": f"Request {request_id} not found"}

        success = self.mlops_service.approval.approve(
            request_id=request_id,
            approver=approver,
            stage=request.current_stage,
        )

        return {
            "status": "approved" if success else "failed",
            "request_id": request_id,
            "approver": approver,
            "current_stage": request.current_stage.value,
            "overall_status": request.overall_status.value,
        }

    # ------------------------------------------------------------------
    # GET /api/v1/mlops/lifecycle/{model_name}
    # ------------------------------------------------------------------

    def get_lifecycle(self, model_name: str = "") -> Dict[str, Any]:
        """Get the lifecycle record and audit trail for a model.

        Returns:
            Lifecycle details with full event history.
        """
        if not self.mlops_service:
            return {"status": "error", "message": "MLOps service not configured"}

        if not model_name:
            return {"status": "error", "message": "model_name required"}

        record = self.mlops_service.lifecycle.get_record(model_name)
        if not record:
            return {
                "model_name": model_name,
                "status": "not_found",
                "message": "No lifecycle record",
            }

        return record.to_dict()

    # ------------------------------------------------------------------
    # GET /api/v1/mlops/health
    # ------------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        """Get platform health status.

        Returns:
            Health check result with component statuses.
        """
        if not self.mlops_service:
            return {"status": "ok", "mlops_service": "not_configured"}

        return self.mlops_service.health_check()

    # ------------------------------------------------------------------
    # GET /api/v1/mlops/pipelines
    # ------------------------------------------------------------------

    def list_pipelines(self, limit: int = 20) -> Dict[str, Any]:
        """List recent pipeline runs.

        Returns:
            List of pipeline run summaries.
        """
        if not self.mlops_service:
            return {"status": "error", "message": "MLOps service not configured"}

        runs = self.mlops_service.get_pipeline_history(limit=limit)
        return {
            "total": len(runs),
            "runs": [r.to_dict() for r in runs],
        }

    # ------------------------------------------------------------------
    # POST /api/v1/mlops/rollback
    # ------------------------------------------------------------------

    def rollback(
        self,
        model_name: str = "",
        to_version: Optional[str] = None,
        reason: str = "Manual rollback via API",
    ) -> Dict[str, Any]:
        """Trigger a manual model rollback.

        Returns:
            Rollback event info.
        """
        if not self.mlops_service:
            return {"status": "error", "message": "MLOps service not configured"}

        if not model_name:
            return {"status": "error", "message": "model_name required"}

        event = self.mlops_service.rollback_manager.rollback(
            model_name=model_name,
            to_version=to_version,
            reason=reason,
        )

        if not event:
            return {"status": "error", "message": "Rollback failed"}

        return {
            "status": "triggered",
            "event_id": event.event_id,
            "model_name": model_name,
            "from_version": event.from_version,
            "to_version": event.to_version,
            "reason": reason,
        }

    # ------------------------------------------------------------------
    # GET /api/v1/mlops/status
    # ------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Get comprehensive MLOps platform status.

        Returns:
            Full status overview.
        """
        if not self.mlops_service:
            return {"status": "error", "message": "MLOps service not configured"}

        service = self.mlops_service

        return {
            "health": service.health_check(),
            "champion": self.get_champion(),
            "active_jobs": len(service.trainer.get_active_jobs()),
            "pending_approvals": service.approval.get_pending_count(),
            "active_deployments": len(service.deployer.get_active_deployments()),
            "lifecycle_stats": service.lifecycle.get_statistics(),
            "scheduled_entries": len(service.scheduler.list_entries()),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log(self, endpoint: str, data: Dict[str, Any]) -> None:
        self._request_log.append({
            "endpoint": endpoint,
            "data": data,
            "timestamp": time.time(),
        })

    def get_request_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent API request log."""
        return self._request_log[-limit:]
