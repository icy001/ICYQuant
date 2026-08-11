"""Research Planner — Plans autonomous research execution from hypotheses.

Takes validated hypotheses and produces structured research plans:
data collection, feature engineering, experiment design, and
validation rules.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Types of research tasks."""

    DATA_COLLECTION = "data_collection"
    FEATURE_ENGINEERING = "feature_engineering"
    FACTOR_COMPUTATION = "factor_computation"
    MODEL_TRAINING = "model_training"
    BACKTEST = "backtest"
    VALIDATION = "validation"
    REPORT = "report"


class ResearchPlanner:
    """Research Planner — creates research plans from hypotheses.

    For each valid hypothesis, the planner produces:
        - Data tasks (what data to collect)
        - Feature tasks (what features to compute)
        - Factor tasks (what factors to build)
        - Experiment tasks (what to test)
        - Validation rules (pass/fail criteria)

    Research Plan structure:
        ├── Hypothesis reference
        ├── Dataset specification
        ├── Feature plan
        ├── Experiment plan
        ├── Metrics
        └── Validation rules
    """

    def __init__(self) -> None:
        self._plans: List[Dict[str, Any]] = []

    async def plan(
        self,
        hypothesis: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Create a research plan for a hypothesis.

        Args:
            hypothesis: A validated hypothesis.

        Returns:
            Structured research plan.
        """
        hyp_id = hypothesis.get("hypothesis_id", "unknown")
        plan_id = f"plan_{hyp_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        plan = {
            "plan_id": plan_id,
            "hypothesis_id": hyp_id,
            "hypothesis_statement": hypothesis.get("statement", ""),
            "status": "created",
            "created_at": datetime.now(timezone.utc).isoformat(),
            # Data Plan
            "dataset": self._plan_dataset(hypothesis),
            # Feature Plan
            "features": hypothesis.get("required_features", []),
            "feature_plan": self._plan_features(hypothesis),
            # Experiment Plan
            "experiments": self._plan_experiments(hypothesis),
            # Factor Plan
            "factor_plan": self._plan_factors(hypothesis),
            # Backtest Plan
            "backtest_config": self._plan_backtest(hypothesis),
            # Validation Rules
            "validation_rules": self._plan_validation(hypothesis),
            # Tasks
            "tasks": self._generate_tasks(hypothesis),
        }

        self._plans.append(plan)
        logger.info("Research plan created: %s", plan_id)

        return plan

    # ------------------------------------------------------------------
    # Plan Components
    # ------------------------------------------------------------------

    def _plan_dataset(self, hyp: Dict[str, Any]) -> Dict[str, Any]:
        """Plan dataset requirements."""
        return {
            "universe": hyp.get("universe", []),
            "timeframe": hyp.get("time_horizon", "daily"),
            "lookback_period": "3y",
            "data_types": hyp.get("required_data", ["price", "volume"]),
            "frequency": "daily",
            "adjustments": ["split_adjusted", "dividend_adjusted"],
        }

    def _plan_features(self, hyp: Dict[str, Any]) -> Dict[str, Any]:
        """Plan feature engineering."""
        features = hyp.get("required_features", [])
        return {
            "features": features,
            "feature_count": len(features),
            "transformations": ["standardize", "winsorize"],
            "handle_missing": "forward_fill",
            "feature_store_version": "latest",
        }

    def _plan_experiments(self, hyp: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Plan experiments to test the hypothesis."""
        experiments = []

        # Primary experiment: test the main hypothesis
        experiments.append({
            "experiment_id": f"exp_{hyp.get('hypothesis_id', '')}_primary",
            "name": f"Test: {hyp.get('statement', '')[:60]}",
            "type": "primary",
            "method": "cross_sectional_regression",
            "target": "forward_returns",
            "horizon": hyp.get("time_horizon", "short_term"),
            "expected_direction": hyp.get("expected_direction", ""),
        })

        # Robustness experiment
        experiments.append({
            "experiment_id": f"exp_{hyp.get('hypothesis_id', '')}_robustness",
            "name": f"Robustness: {hyp.get('statement', '')[:60]}",
            "type": "robustness",
            "method": "panel_regression",
            "controls": ["market_cap", "sector", "volatility"],
            "sub_periods": True,
        })

        return experiments

    def _plan_factors(self, hyp: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Plan factor construction."""
        opportunity_type = hyp.get("opportunity_type", "")

        factor_plans = {
            "momentum": [
                {"name": "price_momentum", "lookback": "21d", "decay": "linear"},
                {"name": "volume_momentum", "lookback": "10d", "decay": "exponential"},
            ],
            "volatility": [
                {"name": "realized_volatility", "lookback": "20d"},
                {"name": "volatility_of_volatility", "lookback": "60d"},
            ],
        }

        return factor_plans.get(opportunity_type, [
            {"name": "custom_factor", "from_features": hyp.get("required_features", [])},
        ])

    def _plan_backtest(self, hyp: Dict[str, Any]) -> Dict[str, Any]:
        """Plan backtest configuration."""
        return {
            "method": "walk_forward",
            "train_window": "2y",
            "test_window": "6m",
            "step_size": "3m",
            "rebalance_frequency": "monthly",
            "transaction_costs": 0.001,
            "slippage": 0.0005,
        }

    def _plan_validation(self, hyp: Dict[str, Any]) -> Dict[str, Any]:
        """Plan validation rules."""
        return {
            "min_ic": 0.02,
            "min_sharpe": 0.5,
            "max_drawdown": -0.30,
            "min_t_stat": 2.0,
            "out_of_sample_required": True,
            "min_oos_periods": 12,
            "falsification": hyp.get("falsification_criteria", ""),
        }

    def _generate_tasks(self, hyp: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate individual research tasks."""
        hyp_id = hyp.get("hypothesis_id", "")
        return [
            {
                "task_id": f"task_{hyp_id}_data",
                "type": TaskType.DATA_COLLECTION.value,
                "description": f"Collect data for {hyp.get('statement', '')[:60]}",
                "status": "pending",
            },
            {
                "task_id": f"task_{hyp_id}_features",
                "type": TaskType.FEATURE_ENGINEERING.value,
                "description": f"Compute features for {hyp.get('statement', '')[:60]}",
                "status": "pending",
            },
            {
                "task_id": f"task_{hyp_id}_backtest",
                "type": TaskType.BACKTEST.value,
                "description": f"Run backtest for {hyp.get('statement', '')[:60]}",
                "status": "pending",
            },
            {
                "task_id": f"task_{hyp_id}_validate",
                "type": TaskType.VALIDATION.value,
                "description": f"Validate results for {hyp.get('statement', '')[:60]}",
                "status": "pending",
            },
        ]
