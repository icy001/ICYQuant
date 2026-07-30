"""RL Service — unified orchestrator for the RL trading system.

Provides a single entry point to manage the complete RL workflow:
- Training pipeline (data → env → train → evaluate → deploy)
- Inference (load policy → predict action)
- Simulation (what-if scenario analysis)
- Portfolio optimization
- Agent self-play management
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum
import time
import uuid
import json
import threading
import logging

import numpy as np

from .environment import (
    RLTradingEnvironment, EnvironmentConfig, EnvironmentMode,
    MarketState, EnvironmentEpisode,
)
from .simulator import TradingSimulator, SimulatorConfig, TradeResult, OrderSide, OrderType
from .reward_engine import RewardEngine, RewardConfig, RewardType
from .state_encoder import StateEncoder, EncoderConfig, EncodedState
from .action_space import (
    ActionSpace, DiscreteActionSpace, ContinuousActionSpace,
    ActionType, ActionConfig,
)
from .policy_network import PolicyNetwork, PolicyConfig, ActorCriticNetwork, NetworkType
from .trainer import RLTrainer, TrainerConfig, TrainingResult, AlgorithmType, TrainingMetrics
from .evaluator import RLEvaluator, EvaluatorConfig, EvaluationResult, EvaluationMetrics
from .agent_selfplay import SelfPlayManager, SelfPlayConfig, SelfPlayAgent, CompetitionResult, AgentStrategy
from .regime_adapter import RegimeAdapter, RegimeConfig, MarketRegime, RegimePolicy
from .portfolio_optimizer import (
    RLPortfolioOptimizer, OptimizerConfig, PortfolioAllocation,
    AllocationResult, OptimizerMethod,
)

logger = logging.getLogger(__name__)


class RLServiceStatus(Enum):
    """Service lifecycle status."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    TRAINING = "training"
    EVALUATING = "evaluating"
    SERVING = "serving"
    STOPPED = "stopped"
    ERROR = "error"


class TrainingJobStatus(Enum):
    """Status of a training job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingJob:
    """A training job managed by the service."""

    job_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    algorithm: AlgorithmType = AlgorithmType.PPO
    status: TrainingJobStatus = TrainingJobStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    # Configuration
    env_config: Optional[EnvironmentConfig] = None
    policy_config: Optional[PolicyConfig] = None
    trainer_config: Optional[TrainerConfig] = None
    reward_config: Optional[RewardConfig] = None

    # Results
    result: Optional[TrainingResult] = None
    error_message: Optional[str] = None

    # Progress
    current_step: int = 0
    total_steps: int = 0
    best_reward: float = 0.0

    def progress_pct(self) -> float:
        if self.total_steps > 0:
            return self.current_step / self.total_steps * 100
        return 0.0


@dataclass
class RLServiceConfig:
    """Configuration for the RL Service."""

    # Service identity
    service_name: str = "rl_trading_service"
    version: str = "0.1.0"

    # Components
    env_config: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    sim_config: SimulatorConfig = field(default_factory=SimulatorConfig)
    reward_config: RewardConfig = field(default_factory=RewardConfig)
    encoder_config: EncoderConfig = field(default_factory=EncoderConfig)
    policy_config: PolicyConfig = field(default_factory=PolicyConfig)
    trainer_config: TrainerConfig = field(default_factory=TrainerConfig)
    evaluator_config: EvaluatorConfig = field(default_factory=EvaluatorConfig)
    selfplay_config: SelfPlayConfig = field(default_factory=SelfPlayConfig)
    regime_config: RegimeConfig = field(default_factory=RegimeConfig)
    optimizer_config: OptimizerConfig = field(default_factory=OptimizerConfig)

    # API
    host: str = "0.0.0.0"
    port: int = 8500
    max_parallel_jobs: int = 4
    job_timeout_seconds: int = 3600

    # Model storage
    model_dir: str = "./rl_models"
    save_best_only: bool = True
    auto_deploy: bool = False

    seed: int = 42


class RLService:
    """Unified RL Trading Service.

    Manages the complete lifecycle of RL-based trading operations:
    - Environment management
    - Policy training and evaluation
    - Agent self-play tournaments
    - Portfolio optimization
    - Online inference
    - Model serving

    Usage:
        service = RLService(config)
        service.initialize()

        # Train
        job = service.start_training()
        service.wait_for_job(job.job_id)

        # Predict
        action = service.predict(state)

        # Optimize portfolio
        allocation = service.optimize_portfolio(prices, current_weights)

        # Run self-play
        results = service.run_selfplay()

        service.shutdown()
    """

    def __init__(self, config: Optional[RLServiceConfig] = None):
        self.config = config or RLServiceConfig()
        self._status = RLServiceStatus.IDLE
        self._lock = threading.Lock()

        # Components (lazy initialization)
        self._env: Optional[RLTradingEnvironment] = None
        self._simulator: Optional[TradingSimulator] = None
        self._reward_engine: Optional[RewardEngine] = None
        self._state_encoder: Optional[StateEncoder] = None
        self._policy: Optional[PolicyNetwork] = None
        self._trainer: Optional[RLTrainer] = None
        self._evaluator: Optional[RLEvaluator] = None
        self._selfplay_manager: Optional[SelfPlayManager] = None
        self._regime_adapter: Optional[RegimeAdapter] = None
        self._portfolio_optimizer: Optional[RLPortfolioOptimizer] = None

        # State
        self._jobs: Dict[str, TrainingJob] = {}
        self._policies: Dict[str, PolicyNetwork] = {}  # policy_name → policy
        self._training_threads: Dict[str, threading.Thread] = {}
        self._evaluation_history: List[EvaluationResult] = []

    # ── Lifecycle ────────────────────────────────────────────

    def initialize(self):
        """Initialize all service components."""
        with self._lock:
            self._status = RLServiceStatus.INITIALIZING

        self._env = RLTradingEnvironment(self.config.env_config)
        self._simulator = TradingSimulator(self.config.sim_config)
        self._reward_engine = RewardEngine(self.config.reward_config)
        self._state_encoder = StateEncoder(self.config.encoder_config)
        self._policy = PolicyNetwork(self.config.policy_config)
        self._regime_adapter = RegimeAdapter(self.config.regime_config)
        self._portfolio_optimizer = RLPortfolioOptimizer(self.config.optimizer_config)

        self._trainer = RLTrainer(
            self._env, self._policy, self.config.trainer_config, self._reward_engine
        )
        self._evaluator = RLEvaluator(
            self._env, self._policy, self.config.evaluator_config
        )
        self._selfplay_manager = SelfPlayManager(self._env, self.config.selfplay_config)

        self._policies["default"] = self._policy

        import os
        os.makedirs(self.config.model_dir, exist_ok=True)

        with self._lock:
            self._status = RLServiceStatus.IDLE

        logger.info("RL Service initialized successfully")

    def shutdown(self):
        """Gracefully shut down the service."""
        with self._lock:
            self._status = RLServiceStatus.STOPPED

        # Cancel running jobs
        for job_id, thread in list(self._training_threads.items()):
            if thread.is_alive():
                job = self._jobs.get(job_id)
                if job:
                    job.status = TrainingJobStatus.CANCELLED

        logger.info("RL Service shut down")

    @property
    def status(self) -> RLServiceStatus:
        return self._status

    # ── Training ─────────────────────────────────────────────

    def start_training(
        self,
        algorithm: Optional[AlgorithmType] = None,
        policy_name: str = "default",
        env_config: Optional[EnvironmentConfig] = None,
        policy_config: Optional[PolicyConfig] = None,
        trainer_config: Optional[TrainerConfig] = None,
        async_mode: bool = True,
    ) -> TrainingJob:
        """Start a training job.

        Args:
            algorithm: RL algorithm to use
            policy_name: Name for the trained policy
            env_config: Environment configuration override
            policy_config: Policy network configuration override
            trainer_config: Trainer configuration override
            async_mode: If True, run in background thread

        Returns:
            TrainingJob with job ID
        """
        job = TrainingJob(
            algorithm=algorithm or self.config.trainer_config.algorithm,
            env_config=env_config,
            policy_config=policy_config,
            trainer_config=trainer_config,
            reward_config=self.config.reward_config,
            total_steps=(trainer_config or self.config.trainer_config).total_timesteps,
        )

        self._jobs[job.job_id] = job

        if async_mode:
            thread = threading.Thread(
                target=self._run_training,
                args=(job, policy_name),
                daemon=True,
            )
            self._training_threads[job.job_id] = thread
            thread.start()
        else:
            self._run_training(job, policy_name)

        return job

    def _run_training(self, job: TrainingJob, policy_name: str):
        """Execute training in a thread."""
        job.status = TrainingJobStatus.RUNNING
        job.started_at = time.time()

        with self._lock:
            self._status = RLServiceStatus.TRAINING

        try:
            # Override configs
            env = (
                RLTradingEnvironment(job.env_config)
                if job.env_config else self._env
            )
            policy = (
                PolicyNetwork(job.policy_config)
                if job.policy_config else self._policy
            )
            trainer = RLTrainer(
                env, policy,
                job.trainer_config or self.config.trainer_config,
                self._reward_engine,
            )

            # Train with progress callback
            def progress_callback(metrics: TrainingMetrics):
                job.current_step = metrics.total_timesteps
                if metrics.eval_reward_mean > job.best_reward:
                    job.best_reward = metrics.eval_reward_mean

            job.result = trainer.train(callback=progress_callback)
            job.status = TrainingJobStatus.COMPLETED
            job.completed_at = time.time()

            # Save trained policy
            self._policies[policy_name] = policy
            self._save_policy(policy, f"{policy_name}_{job.job_id}")

        except Exception as e:
            job.status = TrainingJobStatus.FAILED
            job.error_message = str(e)
            logger.error(f"Training job {job.job_id} failed: {e}")

        finally:
            if self._status == RLServiceStatus.TRAINING:
                with self._lock:
                    self._status = RLServiceStatus.IDLE

    def get_job(self, job_id: str) -> Optional[TrainingJob]:
        """Get training job by ID."""
        return self._jobs.get(job_id)

    def list_jobs(self) -> List[TrainingJob]:
        """List all training jobs."""
        return list(self._jobs.values())

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running training job."""
        job = self._jobs.get(job_id)
        if job and job.status == TrainingJobStatus.RUNNING:
            job.status = TrainingJobStatus.CANCELLED
            return True
        return False

    def wait_for_job(self, job_id: str, timeout: Optional[float] = None):
        """Wait for a training job to complete."""
        thread = self._training_threads.get(job_id)
        if thread and thread.is_alive():
            thread.join(timeout=timeout)

    # ── Inference ────────────────────────────────────────────

    def predict(
        self,
        state: MarketState,
        policy_name: str = "default",
        deterministic: bool = True,
    ) -> Tuple[np.ndarray, float]:
        """Get action prediction from a trained policy.

        Args:
            state: Current market state
            policy_name: Which policy to use
            deterministic: Use deterministic (eval) mode

        Returns:
            (action, log_prob) tuple
        """
        policy = self._policies.get(policy_name, self._policy)
        if policy is None:
            raise RuntimeError("No policy loaded. Train or load a policy first.")

        # Encode state
        encoded = self._state_encoder.encode(state)
        state_vec = encoded.vector if encoded.vector is not None else state.to_vector()

        action, log_prob = policy.act(state_vec, deterministic=deterministic)
        return action, log_prob

    def predict_action_dict(
        self,
        state: MarketState,
        policy_name: str = "default",
        deterministic: bool = True,
    ) -> Dict[str, float]:
        """Get prediction as a symbol→weight dict."""
        action, _ = self.predict(state, policy_name, deterministic)
        return self._action_to_dict(action)

    # ── Evaluation ───────────────────────────────────────────

    def evaluate(
        self,
        policy_name: str = "default",
        evaluator_config: Optional[EvaluatorConfig] = None,
    ) -> EvaluationResult:
        """Evaluate a trained policy.

        Args:
            policy_name: Which policy to evaluate
            evaluator_config: Evaluation configuration override

        Returns:
            EvaluationResult with comprehensive metrics
        """
        policy = self._policies.get(policy_name, self._policy)
        if policy is None:
            raise RuntimeError("No policy loaded.")

        evaluator = RLEvaluator(
            self._env,
            policy,
            evaluator_config or self.config.evaluator_config,
        )
        result = evaluator.evaluate()
        self._evaluation_history.append(result)
        return result

    def get_evaluation_history(self) -> List[EvaluationResult]:
        """Get all evaluation results."""
        return self._evaluation_history.copy()

    # ── Simulation ───────────────────────────────────────────

    def simulate(
        self,
        orders: List[Dict[str, Any]],
        current_prices: Dict[str, float],
        daily_volumes: Optional[Dict[str, float]] = None,
        volatilities: Optional[Dict[str, float]] = None,
    ) -> List[TradeResult]:
        """Simulate trade execution.

        Args:
            orders: List of order dicts
            current_prices: Current prices per symbol
            daily_volumes: ADV per symbol
            volatilities: Volatility per symbol

        Returns:
            List of TradeResult
        """
        if daily_volumes is None:
            daily_volumes = {s: 1_000_000.0 for s in current_prices}
        if volatilities is None:
            volatilities = {s: 0.3 for s in current_prices}

        return self._simulator.execute_basket(
            orders, current_prices, daily_volumes, volatilities
        )

    # ── Self-Play ────────────────────────────────────────────

    def run_selfplay(
        self,
        config: Optional[SelfPlayConfig] = None,
    ) -> List[CompetitionResult]:
        """Run a multi-agent self-play tournament.

        Args:
            config: Self-play configuration override

        Returns:
            List of CompetitionResult per round
        """
        cfg = config or self.config.selfplay_config
        self._selfplay_manager = SelfPlayManager(self._env, cfg)

        # Add agents based on strategies
        for i, strategy in enumerate(cfg.agent_strategies):
            agent_id = f"agent_{i}_{strategy.value}"
            policy = None
            if strategy == AgentStrategy.RL_TRAINED and self._policies:
                policy = list(self._policies.values())[0]
            self._selfplay_manager.add_agent(agent_id, strategy, policy)

        return self._selfplay_manager.run_tournament()

    def get_selfplay_rankings(self) -> List[Tuple[str, float, float]]:
        """Get current self-play rankings."""
        if self._selfplay_manager:
            return self._selfplay_manager._get_rankings()
        return []

    # ── Portfolio Optimization ───────────────────────────────

    def optimize_portfolio(
        self,
        current_prices: Dict[str, float],
        current_weights: Optional[Dict[str, float]] = None,
        returns_data: Optional[Dict[str, List[float]]] = None,
        volatilities: Optional[Dict[str, float]] = None,
        correlations: Optional[np.ndarray] = None,
        regime: Optional[str] = None,
    ) -> AllocationResult:
        """Optimize portfolio allocation.

        Args:
            current_prices: Current asset prices
            current_weights: Current portfolio weights
            returns_data: Historical returns
            volatilities: Asset volatilities
            correlations: Correlation matrix
            regime: Market regime override

        Returns:
            AllocationResult with optimized weights
        """
        detected_regime = regime
        if detected_regime is None and self._regime_adapter:
            detected_regime = self._regime_adapter.get_current_regime().value

        return self._portfolio_optimizer.optimize(
            current_prices=current_prices,
            current_weights=current_weights,
            returns_data=returns_data,
            volatilities=volatilities,
            correlations=correlations,
            regime=detected_regime or "neutral",
        )

    # ── Regime Detection ────────────────────────────────────

    def detect_regime(
        self,
        prices: List[float],
        returns: List[float],
        volatility: float = 0.2,
        drawdown: float = 0.0,
    ) -> MarketRegime:
        """Detect current market regime."""
        return self._regime_adapter.detect_regime(prices, returns, volatility, drawdown)

    def get_regime_distribution(self) -> Dict[str, float]:
        """Get historical regime distribution."""
        return self._regime_adapter.get_regime_distribution()

    # ── Policy Management ───────────────────────────────────

    def get_active_policy(self, name: str = "default") -> Optional[PolicyNetwork]:
        """Get a loaded policy by name."""
        return self._policies.get(name)

    def set_active_policy(self, name: str, policy: PolicyNetwork):
        """Register a policy."""
        self._policies[name] = policy

    def list_policies(self) -> List[str]:
        """List all loaded policy names."""
        return list(self._policies.keys())

    def load_policy(self, name: str, path: str):
        """Load a policy from disk."""
        policy = PolicyNetwork(self.config.policy_config)
        policy.load(path)
        self._policies[name] = policy
        logger.info(f"Loaded policy '{name}' from {path}")

    def save_policy(self, name: str, path: Optional[str] = None):
        """Save a policy to disk."""
        policy = self._policies.get(name)
        if policy is None:
            raise ValueError(f"Policy '{name}' not found")

        if path is None:
            import os
            path = os.path.join(self.config.model_dir, f"{name}.pkl")

        policy.save(path)
        logger.info(f"Saved policy '{name}' to {path}")

    def _save_policy(self, policy: PolicyNetwork, name: str):
        """Internal save with directory handling."""
        import os
        path = os.path.join(self.config.model_dir, f"{name}.pkl")
        policy.save(path)

    def _action_to_dict(self, action: np.ndarray) -> Dict[str, float]:
        """Convert action array to symbol→weight dict."""
        symbols = self.config.env_config.symbols
        return {
            s: float(action[i]) if i < len(action) else 0.0
            for i, s in enumerate(symbols)
        }

    # ── Status / Monitoring ──────────────────────────────────

    def get_service_status(self) -> Dict[str, Any]:
        """Get comprehensive service status."""
        return {
            "status": self._status.value,
            "service_name": self.config.service_name,
            "version": self.config.version,
            "num_policies": len(self._policies),
            "policy_names": list(self._policies.keys()),
            "num_jobs": len(self._jobs),
            "active_jobs": sum(
                1 for j in self._jobs.values()
                if j.status == TrainingJobStatus.RUNNING
            ),
            "completed_jobs": sum(
                1 for j in self._jobs.values()
                if j.status == TrainingJobStatus.COMPLETED
            ),
            "current_regime": (
                self._regime_adapter.get_current_regime().value
                if self._regime_adapter else "unknown"
            ),
        }

    def get_training_stats(self) -> Dict[str, Any]:
        """Get training statistics."""
        if not self._trainer:
            return {}

        metrics = self._trainer.get_metrics()
        return metrics.to_dict()
