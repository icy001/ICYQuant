"""Serving API — REST endpoint controller for model serving.

Provides the HTTP API endpoints for prediction, model management,
deployment, A/B testing, and monitoring.

Endpoints:
    POST /api/v1/inference/predict       - Online prediction
    POST /api/v1/inference/predict/batch - Batch prediction
    GET  /api/v1/inference/model         - Model status
    POST /api/v1/inference/deploy        - Deploy model
    POST /api/v1/inference/rollback      - Rollback model
    GET  /api/v1/inference/health         - Health check
    GET  /api/v1/inference/stats          - Monitoring stats
    POST /api/v1/inference/ab/create      - Create A/B experiment
    POST /api/v1/inference/ab/start       - Start A/B experiment
    GET  /api/v1/inference/ab/result      - Get A/B results
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class ServingAPI:
    """Controller for serving API endpoints.

    Provides a Python-native interface for all serving endpoints
    that can be exported to FastAPI, Flask, or gRPC.

    Usage::

        api = ServingAPI(serving_service)
        result = api.predict("NVDA")
        status = api.get_model_status()
    """

    def __init__(self, serving_service: Any = None):
        self._service = serving_service

    # ---- Prediction ----

    def predict(
        self,
        symbol: str,
        features: Optional[Dict[str, float]] = None,
        model_name: Optional[str] = None,
        market: str = "US",
    ) -> Dict[str, Any]:
        """Single online prediction.

        POST /api/v1/inference/predict
        """
        if not self._service:
            return {"error": "Serving service not configured"}

        result = self._service.predict(
            symbol=symbol,
            features=features,
            model_name=model_name,
            market=market,
        )

        return result.to_dict() if hasattr(result, 'to_dict') else {
            "symbol": symbol,
            "prediction": result.prediction if hasattr(result, 'prediction') else result,
            "confidence": getattr(result, 'confidence', None),
        }

    def predict_batch(
        self,
        symbols: List[str],
        features_list: Optional[List[Dict[str, float]]] = None,
        market: str = "US",
    ) -> Dict[str, Any]:
        """Batch prediction.

        POST /api/v1/inference/predict/batch
        """
        if not self._service:
            return {"error": "Serving service not configured"}

        results = self._service.predict_batch(
            symbols=symbols,
            features_list=features_list,
            market=market,
        )

        return {
            "results": [r.to_dict() if hasattr(r, 'to_dict') else {"prediction": r.prediction} for r in results],
        }

    def predict_portfolio(
        self,
        symbols: List[str],
        features_dict: Optional[Dict[str, Dict[str, float]]] = None,
        market: str = "US",
    ) -> Dict[str, Any]:
        """Portfolio-level prediction.

        POST /api/v1/inference/predict/portfolio
        """
        if not self._service:
            return {"error": "Serving service not configured"}

        results = self._service.predict_portfolio(symbols, features_dict, market)
        return {
            symbol: r.to_dict() if hasattr(r, 'to_dict') else {"prediction": r.prediction}
            for symbol, r in results.items()
        }

    # ---- Model Management ----

    def get_model_status(self) -> Dict[str, Any]:
        """Get serving model status.

        GET /api/v1/inference/model
        """
        if not self._service:
            return {"error": "Serving service not configured"}

        status = self._service.get_status()

        active = status.get("active_versions", {})
        models = status.get("models", [])

        return {
            "mode": status.get("mode", "unknown"),
            "total_loaded": len(models),
            "active_versions": active,
            "models": models,
        }

    def deploy(
        self,
        model: str,
        version: str = "",
        strategy: str = "immediate",
    ) -> Dict[str, Any]:
        """Deploy a model for serving.

        POST /api/v1/inference/deploy
        """
        if not self._service:
            return {"error": "Serving service not configured"}

        result = self._service.deploy(model, version, strategy=strategy)

        return {
            "model": result.model_name if hasattr(result, 'model_name') else model,
            "version": result.version if hasattr(result, 'version') else version,
            "strategy": strategy,
            "success": result.success if hasattr(result, 'success') else True,
            "message": result.message if hasattr(result, 'message') else "Deployed",
        }

    def rollback(self, model: str) -> Dict[str, Any]:
        """Rollback a model to previous version.

        POST /api/v1/inference/rollback
        """
        if not self._service:
            return {"error": "Serving service not configured"}

        result = self._service.rollback(model)

        return {
            "model": model,
            "success": result.success if hasattr(result, 'success') else True,
            "message": result.message if hasattr(result, 'message') else "Rolled back",
        }

    # ---- Health & Monitoring ----

    def health(self) -> Dict[str, Any]:
        """Health check.

        GET /api/v1/inference/health
        """
        if not self._service:
            return {"status": "not_configured"}

        health = self._service.health()
        return {
            "status": health.value if hasattr(health, 'value') else str(health),
        }

    def stats(self) -> Dict[str, Any]:
        """Get serving statistics.

        GET /api/v1/inference/stats
        """
        if not self._service:
            return {"error": "Serving service not configured"}
        return self._service.get_monitor_stats()

    # ---- A/B Testing ----

    def create_ab_test(
        self,
        name: str,
        variants: List[Dict[str, Any]],
        description: str = "",
    ) -> Dict[str, Any]:
        """Create an A/B testing experiment.

        POST /api/v1/inference/ab/create
        """
        if not self._service:
            return {"error": "Serving service not configured"}
        if not self._service.ab_testing:
            return {"error": "A/B testing not enabled"}

        exp = self._service.create_ab_experiment(name, variants, description)
        return {
            "experiment_id": exp.experiment_id if exp else "",
            "name": name,
            "variants": len(variants),
            "created": True,
        }

    def start_ab_test(self, name: str) -> Dict[str, Any]:
        """Start an A/B testing experiment.

        POST /api/v1/inference/ab/start
        """
        if not self._service or not self._service.ab_testing:
            return {"error": "A/B testing not enabled"}

        self._service.ab_testing.start(name)
        return {"experiment": name, "status": "running"}

    def get_ab_results(self, name: str) -> Dict[str, Any]:
        """Get A/B testing results.

        GET /api/v1/inference/ab/result
        """
        if not self._service or not self._service.ab_testing:
            return {"error": "A/B testing not enabled"}

        results = self._service.ab_testing.get_results(name)
        return {
            "experiment": name,
            "variants": {k: v.to_dict() for k, v in results.items()},
        }

    def complete_ab_test(self, name: str, winner: Optional[str] = None) -> Dict[str, Any]:
        """Complete an A/B experiment.

        POST /api/v1/inference/ab/complete
        """
        if not self._service or not self._service.ab_testing:
            return {"error": "A/B testing not enabled"}

        return self._service.ab_testing.complete(name, winner)

    # ---- Canary ----

    def get_canary_status(self) -> Dict[str, Any]:
        """Get canary rollout status.

        GET /api/v1/inference/canary
        """
        if not self._service or not self._service.canary:
            return {"error": "Canary not enabled"}

        s = self._service.canary.status
        return {
            "model_name": s.model_name,
            "stage": s.current_stage.value if hasattr(s.current_stage, 'value') else str(s.current_stage),
            "traffic_share": s.traffic_share,
            "state": s.state.value if hasattr(s.state, 'value') else str(s.state),
        }

    def advance_canary(self) -> Dict[str, Any]:
        """Advance canary to next stage.

        POST /api/v1/inference/canary/advance
        """
        if not self._service or not self._service.canary:
            return {"error": "Canary not enabled"}

        status = self._service.canary.advance()
        return {
            "stage": status.current_stage.value if hasattr(status.current_stage, 'value') else str(status.current_stage),
            "traffic_share": status.traffic_share,
            "state": status.state.value if hasattr(status.state, 'value') else str(status.state),
        }

    def rollback_canary(self) -> Dict[str, Any]:
        """Immediate canary rollback.

        POST /api/v1/inference/canary/rollback
        """
        if not self._service or not self._service.canary:
            return {"error": "Canary not enabled"}

        status = self._service.canary.rollback()
        return {"state": status.state.value if hasattr(status.state, 'value') else str(status.state)}

    # ---- Cache ----

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get prediction cache statistics.

        GET /api/v1/inference/cache
        """
        if not self._service:
            return {"error": "Serving service not configured"}
        if self._service.cache:
            return self._service.cache.get_stats()
        return {"error": "Cache not enabled"}

    def invalidate_cache(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Invalidate prediction cache.

        POST /api/v1/inference/cache/invalidate
        """
        if not self._service or not self._service.cache:
            return {"error": "Cache not enabled"}

        if symbol:
            self._service.cache.invalidate(symbol)
            return {"invalidated": symbol}
        else:
            count = self._service.cache.invalidate_all()
            return {"invalidated": count}
