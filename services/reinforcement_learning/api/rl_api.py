"""REST API for the RL Trading Service.

Provides HTTP endpoints for:
- Training job management
- Policy inference
- Simulation
- Portfolio optimization
- Self-play tournament control
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum
import json
import uuid
import logging

import numpy as np

from ..environment import MarketState, EnvironmentConfig
from ..service import (
    RLService, RLServiceConfig, RLServiceStatus,
    TrainingJob, TrainingJobStatus,
)
from ..trainer import AlgorithmType, TrainerConfig
from ..evaluator import EvaluatorConfig, EvaluationResult
from ..portfolio_optimizer import OptimizerConfig, OptimizerMethod
from ..agent_selfplay import SelfPlayConfig, AgentStrategy
from ..policy_network import PolicyConfig

logger = logging.getLogger(__name__)


@dataclass
class APIResponse:
    """Standard API response wrapper."""

    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    message: Optional[str] = None
    request_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error is not None:
            result["error"] = self.error
        if self.message is not None:
            result["message"] = self.message
        if self.request_id is not None:
            result["request_id"] = self.request_id
        return result


@dataclass
class TrainRequest:
    """Request to start a training job."""

    algorithm: str = "ppo"  # ppo, sac, dqn, a2c
    env_config: Optional[Dict[str, Any]] = None
    policy_config: Optional[Dict[str, Any]] = None
    trainer_config: Optional[Dict[str, Any]] = None

    # Training hyperparameters
    total_timesteps: int = 1_000_000
    batch_size: int = 64
    learning_rate: float = 3e-4

    # Environment
    symbols: List[str] = field(default_factory=lambda: ["AAPL", "MSFT", "NVDA"])
    initial_balance: float = 1_000_000.0

    async_mode: bool = True
    policy_name: str = "default"


@dataclass
class PredictRequest:
    """Request for policy prediction."""

    state: Dict[str, Any]  # MarketState serialized
    policy_name: str = "default"
    deterministic: bool = True


@dataclass
class OptimizeRequest:
    """Request for portfolio optimization."""

    current_prices: Dict[str, float]
    current_weights: Optional[Dict[str, float]] = None
    returns_data: Optional[Dict[str, List[float]]] = None
    volatilities: Optional[Dict[str, float]] = None
    regime: Optional[str] = None
    method: Optional[str] = None


@dataclass
class SimulateRequest:
    """Request for trade simulation."""

    orders: List[Dict[str, Any]]
    current_prices: Dict[str, float]
    daily_volumes: Optional[Dict[str, float]] = None
    volatilities: Optional[Dict[str, float]] = None


@dataclass
class SelfPlayRequest:
    """Request to run self-play tournament."""

    n_agents: int = 4
    n_rounds: int = 100
    strategies: Optional[List[str]] = None
    rl_policy_name: Optional[str] = None


class RLAPI:
    """REST API layer for the RL Trading Service.

    Provides a clean Python API that can be exposed via
    FastAPI/Flask/Django REST endpoints.

    Usage:
        service = RLService(config)
        service.initialize()

        api = RLAPI(service)

        # Train
        response = api.train(TrainRequest(algorithm="ppo"))

        # Predict
        response = api.predict(PredictRequest(state=state_dict))

        # Optimize portfolio
        response = api.optimize_portfolio(OptimizeRequest(
            current_prices={"AAPL": 150.0, "MSFT": 300.0}
        ))
    """

    def __init__(self, service: Optional[RLService] = None):
        """Initialize API with an RL service.

        Args:
            service: RLService instance. Creates a default one if None.
        """
        self._service = service or RLService()
        if service is None:
            self._service.initialize()

    @property
    def service(self) -> RLService:
        return self._service

    # ── Health ───────────────────────────────────────────────

    def health(self) -> APIResponse:
        """Health check endpoint."""
        try:
            status = self._service.get_service_status()
            return APIResponse(
                success=True,
                data=status,
                message="Service is healthy",
            )
        except Exception as e:
            return APIResponse(
                success=False,
                error=str(e),
                message="Service health check failed",
            )

    # ── Training ─────────────────────────────────────────────

    def train(self, request: TrainRequest) -> APIResponse:
        """Start a training job.

        POST /api/v1/rl/train
        """
        try:
            # Map algorithm string to enum
            algo_map = {
                "ppo": AlgorithmType.PPO,
                "sac": AlgorithmType.SAC,
                "dqn": AlgorithmType.DQN,
                "a2c": AlgorithmType.A2C,
                "td3": AlgorithmType.TD3,
            }
            algorithm = algo_map.get(request.algorithm.lower(), AlgorithmType.PPO)

            # Build configs from request
            env_config = EnvironmentConfig(
                symbols=request.symbols,
                initial_balance=request.initial_balance,
            )

            trainer_config = TrainerConfig(
                algorithm=algorithm,
                total_timesteps=request.total_timesteps,
                batch_size=request.batch_size,
            )

            policy_config = PolicyConfig(
                state_dim=len(request.symbols) * 5 + 6,
                action_dim=len(request.symbols),
            )

            # Apply overrides from request
            if request.env_config:
                for k, v in request.env_config.items():
                    if hasattr(env_config, k):
                        setattr(env_config, k, v)
            if request.trainer_config:
                for k, v in request.trainer_config.items():
                    if hasattr(trainer_config, k):
                        setattr(trainer_config, k, v)
            if request.policy_config:
                for k, v in request.policy_config.items():
                    if hasattr(policy_config, k):
                        setattr(policy_config, k, v)

            job = self._service.start_training(
                algorithm=algorithm,
                policy_name=request.policy_name,
                env_config=env_config,
                policy_config=policy_config,
                trainer_config=trainer_config,
                async_mode=request.async_mode,
            )

            return APIResponse(
                success=True,
                data={
                    "job_id": job.job_id,
                    "status": job.status.value,
                    "algorithm": algorithm.value,
                    "total_steps": job.total_steps,
                },
                message=f"Training job {job.job_id} started",
            )
        except Exception as e:
            logger.error(f"Train request failed: {e}")
            return APIResponse(success=False, error=str(e))

    def get_job_status(self, job_id: str) -> APIResponse:
        """Get training job status.

        GET /api/v1/rl/jobs/{job_id}
        """
        try:
            job = self._service.get_job(job_id)
            if job is None:
                return APIResponse(
                    success=False,
                    error=f"Job {job_id} not found",
                )

            return APIResponse(
                success=True,
                data={
                    "job_id": job.job_id,
                    "status": job.status.value,
                    "algorithm": job.algorithm.value,
                    "progress_pct": job.progress_pct(),
                    "current_step": job.current_step,
                    "total_steps": job.total_steps,
                    "best_reward": job.best_reward,
                    "error": job.error_message,
                },
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def list_jobs(self) -> APIResponse:
        """List all training jobs.

        GET /api/v1/rl/jobs
        """
        try:
            jobs = self._service.list_jobs()
            return APIResponse(
                success=True,
                data={
                    "jobs": [
                        {
                            "job_id": j.job_id,
                            "status": j.status.value,
                            "algorithm": j.algorithm.value,
                            "progress_pct": j.progress_pct(),
                            "best_reward": j.best_reward,
                        }
                        for j in jobs
                    ],
                    "total": len(jobs),
                },
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def cancel_job(self, job_id: str) -> APIResponse:
        """Cancel a training job.

        DELETE /api/v1/rl/jobs/{job_id}
        """
        try:
            cancelled = self._service.cancel_job(job_id)
            return APIResponse(
                success=cancelled,
                message=f"Job {job_id} {'cancelled' if cancelled else 'not found or not running'}",
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def wait_for_job(self, job_id: str, timeout: Optional[float] = None) -> APIResponse:
        """Wait for a job to complete and return results.

        GET /api/v1/rl/jobs/{job_id}/wait?timeout=300
        """
        try:
            self._service.wait_for_job(job_id, timeout=timeout)
            job = self._service.get_job(job_id)
            if job is None:
                return APIResponse(success=False, error=f"Job {job_id} not found")

            response_data = {
                "job_id": job.job_id,
                "status": job.status.value,
            }

            if job.result:
                response_data["metrics"] = job.result.metrics.to_dict()
                response_data["best_reward"] = job.result.best_reward
                response_data["convergence_step"] = job.result.convergence_step

            return APIResponse(success=True, data=response_data)

        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ── Prediction ───────────────────────────────────────────

    def predict(self, request: PredictRequest) -> APIResponse:
        """Get action prediction.

        POST /api/v1/rl/predict
        """
        try:
            # Deserialize state
            state = self._deserialize_state(request.state)
            action, log_prob = self._service.predict(
                state=state,
                policy_name=request.policy_name,
                deterministic=request.deterministic,
            )

            return APIResponse(
                success=True,
                data={
                    "action": action.tolist() if isinstance(action, np.ndarray) else action,
                    "log_prob": log_prob,
                    "policy_name": request.policy_name,
                },
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ── Evaluation ───────────────────────────────────────────

    def evaluate(self, policy_name: str = "default") -> APIResponse:
        """Evaluate a policy.

        GET /api/v1/rl/evaluate?policy_name=default
        """
        try:
            result = self._service.evaluate(policy_name=policy_name)
            return APIResponse(
                success=True,
                data={
                    "metrics": result.metrics.to_dict(),
                    "passed": result.passed,
                    "warnings": result.warnings,
                },
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ── Simulation ───────────────────────────────────────────

    def simulate(self, request: SimulateRequest) -> APIResponse:
        """Simulate trade execution.

        POST /api/v1/rl/simulate
        """
        try:
            results = self._service.simulate(
                orders=request.orders,
                current_prices=request.current_prices,
                daily_volumes=request.daily_volumes,
                volatilities=request.volatilities,
            )

            trades = []
            for r in results:
                trades.append({
                    "symbol": r.symbol,
                    "side": r.side.value,
                    "filled_quantity": r.filled_quantity,
                    "fill_price": r.fill_price,
                    "commission": r.commission,
                    "slippage_cost": r.slippage_cost,
                    "impact_cost": r.impact_cost,
                    "total_cost": r.total_cost,
                    "fill_ratio": r.fill_ratio,
                    "success": r.success,
                })

            total_cost = sum(r.total_cost for r in results)
            avg_fill = (
                sum(r.fill_ratio for r in results) / len(results)
                if results else 0.0
            )

            return APIResponse(
                success=True,
                data={
                    "trades": trades,
                    "num_trades": len(trades),
                    "total_cost": total_cost,
                    "avg_fill_ratio": avg_fill,
                },
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ── Portfolio Optimization ───────────────────────────────

    def optimize_portfolio(self, request: OptimizeRequest) -> APIResponse:
        """Optimize portfolio allocation.

        POST /api/v1/rl/optimize
        """
        try:
            result = self._service.optimize_portfolio(
                current_prices=request.current_prices,
                current_weights=request.current_weights,
                returns_data=request.returns_data,
                volatilities=request.volatilities,
                regime=request.regime,
            )

            return APIResponse(
                success=True,
                data={
                    "allocation": result.allocation.to_dict(),
                    "regime": result.regime,
                    "confidence": result.confidence,
                    "warnings": result.warnings,
                    "comparison": result.comparison,
                },
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ── Self-Play ────────────────────────────────────────────

    def run_selfplay(self, request: Optional[SelfPlayRequest] = None) -> APIResponse:
        """Run self-play tournament.

        POST /api/v1/rl/selfplay
        """
        try:
            req = request or SelfPlayRequest()

            # Map strategy names
            strategy_map = {
                "trend": AgentStrategy.TREND_FOLLOWING,
                "mean_reversion": AgentStrategy.MEAN_REVERSION,
                "market_making": AgentStrategy.MARKET_MAKING,
                "momentum": AgentStrategy.MOMENTUM,
                "breakout": AgentStrategy.BREAKOUT,
                "arbitrage": AgentStrategy.ARBITRAGE,
                "buy_hold": AgentStrategy.BUY_HOLD,
                "random": AgentStrategy.RANDOM,
            }

            strategies = (
                [strategy_map.get(s.lower(), AgentStrategy.TREND_FOLLOWING)
                 for s in req.strategies]
                if req.strategies
                else [
                    AgentStrategy.TREND_FOLLOWING,
                    AgentStrategy.MEAN_REVERSION,
                    AgentStrategy.MARKET_MAKING,
                    AgentStrategy.MOMENTUM,
                ]
            )

            config = SelfPlayConfig(
                n_agents=req.n_agents,
                n_rounds=req.n_rounds,
                agent_strategies=strategies,
            )

            results = self._service.run_selfplay(config=config)
            rankings = self._service.get_selfplay_rankings()

            return APIResponse(
                success=True,
                data={
                    "num_rounds": len(results),
                    "rankings": [
                        {"agent_id": a[0], "elo": a[1], "win_rate": a[2]}
                        for a in rankings
                    ],
                    "best_agent": rankings[0][0] if rankings else None,
                    "best_elo": rankings[0][1] if rankings else 0.0,
                },
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ── Regime ───────────────────────────────────────────────

    def detect_regime(
        self,
        prices: List[float],
        returns: List[float],
        volatility: float = 0.2,
        drawdown: float = 0.0,
    ) -> APIResponse:
        """Detect market regime.

        POST /api/v1/rl/regime/detect
        """
        try:
            regime = self._service.detect_regime(
                prices=prices,
                returns=returns,
                volatility=volatility,
                drawdown=drawdown,
            )
            distribution = self._service.get_regime_distribution()

            return APIResponse(
                success=True,
                data={
                    "regime": regime.value,
                    "historical_distribution": distribution,
                },
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ── Policy Management ────────────────────────────────────

    def list_policies(self) -> APIResponse:
        """List loaded policies.

        GET /api/v1/rl/policies
        """
        try:
            policies = self._service.list_policies()
            return APIResponse(
                success=True,
                data={"policies": policies, "count": len(policies)},
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def load_policy(self, name: str, path: str) -> APIResponse:
        """Load a policy from disk.

        POST /api/v1/rl/policies/load
        """
        try:
            self._service.load_policy(name, path)
            return APIResponse(
                success=True,
                message=f"Policy '{name}' loaded from {path}",
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def save_policy(self, name: str, path: Optional[str] = None) -> APIResponse:
        """Save a policy to disk.

        POST /api/v1/rl/policies/save
        """
        try:
            self._service.save_policy(name, path)
            return APIResponse(
                success=True,
                message=f"Policy '{name}' saved",
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ── Service Status ───────────────────────────────────────

    def status(self) -> APIResponse:
        """Get service status.

        GET /api/v1/rl/status
        """
        try:
            service_status = self._service.get_service_status()
            training_stats = self._service.get_training_stats()

            return APIResponse(
                success=True,
                data={
                    "service": service_status,
                    "training": training_stats,
                },
            )
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    def shutdown(self) -> APIResponse:
        """Shut down the service.

        POST /api/v1/rl/shutdown
        """
        try:
            self._service.shutdown()
            return APIResponse(success=True, message="Service shut down")
        except Exception as e:
            return APIResponse(success=False, error=str(e))

    # ── Helpers ──────────────────────────────────────────────

    def _deserialize_state(self, state_dict: Dict[str, Any]) -> MarketState:
        """Deserialize MarketState from dict."""
        return MarketState(
            prices=state_dict.get("prices", {}),
            returns=state_dict.get("returns", {}),
            volumes=state_dict.get("volumes", {}),
            volatility=state_dict.get("volatility", {}),
            spreads=state_dict.get("spreads", {}),
            market_sentiment=state_dict.get("market_sentiment", 0.0),
            market_regime=state_dict.get("market_regime", "neutral"),
            portfolio_value=state_dict.get("portfolio_value", 0.0),
            cash=state_dict.get("cash", 0.0),
            positions=state_dict.get("positions", {}),
            position_pct=state_dict.get("position_pct", {}),
            total_exposure=state_dict.get("total_exposure", 0.0),
            leverage=state_dict.get("leverage", 0.0),
            current_drawdown=state_dict.get("current_drawdown", 0.0),
            portfolio_var=state_dict.get("portfolio_var", 0.0),
            sharpe_ratio=state_dict.get("sharpe_ratio", 0.0),
            step=state_dict.get("step", 0),
        )
