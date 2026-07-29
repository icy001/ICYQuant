"""Experiment Design Engine - structured experiment planning and execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class ExperimentType(Enum):
    """Types of research experiments."""

    BACKTEST = "backtest"
    STATISTICAL_TEST = "statistical_test"
    SIMULATION = "simulation"
    CROSS_VALIDATION = "cross_validation"
    SENSITIVITY = "sensitivity"
    REGIME_ANALYSIS = "regime_analysis"
    WALK_FORWARD = "walk_forward"
    MONTE_CARLO = "monte_carlo"
    BOOTSTRAP = "bootstrap"
    AB_TEST = "ab_test"


class ExperimentStatus(Enum):
    """Experiment lifecycle status."""

    DESIGNED = "designed"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ANALYZED = "analyzed"


@dataclass
class ExperimentDesign:
    """A complete experiment design."""

    id: str = field(default_factory=lambda: uuid4().hex[:12])
    name: str = ""
    experiment_type: ExperimentType = ExperimentType.BACKTEST
    hypothesis_id: Optional[str] = None
    status: ExperimentStatus = ExperimentStatus.DESIGNED
    description: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    methodology: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    evaluation_metrics: List[Dict[str, Any]] = field(default_factory=list)
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    controls: List[Dict[str, Any]] = field(default_factory=list)
    expected_results: Dict[str, Any] = field(default_factory=dict)
    actual_results: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.experiment_type.value,
            "hypothesis_id": self.hypothesis_id,
            "status": self.status.value,
            "description": self.description,
            "input_data": self.input_data,
            "methodology": self.methodology,
            "parameters": self.parameters,
            "evaluation_metrics": self.evaluation_metrics,
            "success_criteria": self.success_criteria,
            "controls": self.controls,
            "expected_results": self.expected_results,
            "actual_results": self.actual_results,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "notes": self.notes,
        }


class ExperimentDesignEngine:
    """Experiment Design Engine.

    Designs rigorous experiments to test research hypotheses.
    Each experiment follows the scientific method:

    1. Define input data specifications
    2. Select appropriate methodology
    3. Set evaluation metrics
    4. Define success criteria
    5. Establish controls and baselines
    6. Specify expected results

    Supports multiple experiment types:
    - Backtesting: strategy performance evaluation
    - Statistical tests: hypothesis validation
    - Simulations: Monte Carlo, bootstrap
    - Cross-validation: model robustness
    - Sensitivity analysis: parameter stability
    - Regime analysis: market condition dependence
    """

    def __init__(self):
        self.experiments: Dict[str, ExperimentDesign] = {}
        self.design_history: List[Dict[str, Any]] = []
        self.methodology_templates: Dict[ExperimentType, Dict[str, Any]] = {
            ExperimentType.BACKTEST: {
                "steps": [
                    "data_preparation", "signal_generation",
                    "portfolio_construction", "performance_calculation",
                    "risk_analysis", "attribution",
                ],
                "required_params": [
                    "start_date", "end_date", "universe",
                    "rebalance_frequency", "transaction_costs",
                ],
                "validation": ["out_of_sample", "walk_forward", "bootstrap"],
            },
            ExperimentType.STATISTICAL_TEST: {
                "steps": [
                    "hypothesis_formulation", "test_selection",
                    "assumption_checking", "calculation",
                    "interpretation",
                ],
                "required_params": [
                    "test_type", "significance_level",
                    "sample_size", "tail_type",
                ],
                "validation": ["power_analysis", "assumption_testing"],
            },
            ExperimentType.SIMULATION: {
                "steps": [
                    "model_specification", "parameter_estimation",
                    "simulation_run", "result_aggregation",
                    "distribution_analysis",
                ],
                "required_params": [
                    "n_simulations", "time_horizon",
                    "random_seed", "model_type",
                ],
                "validation": ["convergence_check", "sensitivity_analysis"],
            },
            ExperimentType.CROSS_VALIDATION: {
                "steps": [
                    "data_splitting", "model_training",
                    "validation", "performance_aggregation",
                    "stability_analysis",
                ],
                "required_params": [
                    "n_folds", "split_method",
                    "shuffle", "stratify",
                ],
                "validation": ["fold_consistency", "bias_check"],
            },
            ExperimentType.SENSITIVITY: {
                "steps": [
                    "parameter_grid_definition", "grid_search",
                    "result_surface", "optimal_region",
                    "stability_assessment",
                ],
                "required_params": [
                    "parameter_ranges", "step_sizes",
                    "n_iterations", "search_method",
                ],
                "validation": ["robustness_check", "boundary_analysis"],
            },
            ExperimentType.REGIME_ANALYSIS: {
                "steps": [
                    "regime_identification", "segmentation",
                    "per_regime_analysis", "comparison",
                    "transition_analysis",
                ],
                "required_params": [
                    "regime_definition", "n_regimes",
                    "transition_model", "min_regime_length",
                ],
                "validation": ["regime_stability", "transition_robustness"],
            },
            ExperimentType.WALK_FORWARD: {
                "steps": [
                    "initial_training", "rolling_forward",
                    "out_of_sample_testing", "performance_tracking",
                    "stability_monitoring",
                ],
                "required_params": [
                    "training_window", "testing_window",
                    "step_size", "min_training_size",
                ],
                "validation": ["stability_check", "overfitting_detection"],
            },
            ExperimentType.MONTE_CARLO: {
                "steps": [
                    "distribution_specification", "random_generation",
                    "path_simulation", "statistic_calculation",
                    "confidence_interval",
                ],
                "required_params": [
                    "n_paths", "time_steps",
                    "distribution_type", "random_seed",
                ],
                "validation": ["convergence_diagnostic", "distribution_fit"],
            },
            ExperimentType.BOOTSTRAP: {
                "steps": [
                    "resampling", "statistic_calculation",
                    "distribution_building", "confidence_interval",
                    "bias_correction",
                ],
                "required_params": [
                    "n_bootstrap", "sample_size",
                    "block_size", "method",
                ],
                "validation": ["bootstrap_convergence", "coverage_check"],
            },
            ExperimentType.AB_TEST: {
                "steps": [
                    "group_assignment", "treatment_application",
                    "metric_collection", "statistical_test",
                    "conclusion",
                ],
                "required_params": [
                    "control_config", "treatment_config",
                    "sample_size", "test_duration",
                ],
                "validation": ["sample_size_check", "balance_check"],
            },
        }

    def design(self, hypothesis: Dict[str, Any]) -> Dict[str, Any]:
        """Design an experiment from a hypothesis."""
        return self.design_experiment(hypothesis).to_dict()

    def design_experiment(
        self,
        hypothesis: Dict[str, Any],
        experiment_type: Optional[ExperimentType] = None,
    ) -> ExperimentDesign:
        """Create a complete experiment design for testing a hypothesis."""
        hypothesis_id = hypothesis.get("id")
        hypothesis_statement = hypothesis.get("statement", "Untitled")

        if experiment_type is None:
            experiment_type = self._select_experiment_type(hypothesis)

        methodology = self.methodology_templates.get(
            experiment_type,
            self.methodology_templates[ExperimentType.STATISTICAL_TEST],
        )

        experiment = ExperimentDesign(
            name=f"Experiment: {hypothesis_statement[:60]}",
            experiment_type=experiment_type,
            hypothesis_id=hypothesis_id,
            description=f"Test hypothesis: {hypothesis_statement}",
            input_data=self._define_input_data(hypothesis, experiment_type),
            methodology={
                "steps": methodology["steps"],
                "required_params": methodology["required_params"],
                "validation_methods": methodology["validation"],
            },
            parameters=self._define_parameters(experiment_type, hypothesis),
            evaluation_metrics=self._define_metrics(hypothesis),
            success_criteria=self._define_success_criteria(hypothesis),
            controls=self._define_controls(experiment_type),
            expected_results=self._define_expected_results(hypothesis),
        )

        self.experiments[experiment.id] = experiment
        self.design_history.append({
            "experiment_id": experiment.id,
            "hypothesis_id": hypothesis_id,
            "type": experiment_type.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return experiment

    def _select_experiment_type(self, hypothesis: Dict[str, Any]) -> ExperimentType:
        type_mapping = {
            "market": ExperimentType.REGIME_ANALYSIS,
            "factor": ExperimentType.CROSS_VALIDATION,
            "strategy": ExperimentType.BACKTEST,
            "relationship": ExperimentType.STATISTICAL_TEST,
            "pattern": ExperimentType.BOOTSTRAP,
            "causal": ExperimentType.STATISTICAL_TEST,
            "predictive": ExperimentType.CROSS_VALIDATION,
        }
        return type_mapping.get(hypothesis.get("type", ""), ExperimentType.STATISTICAL_TEST)

    def _define_input_data(self, hypothesis: Dict[str, Any], etype: ExperimentType) -> Dict[str, Any]:
        data_spec = {
            "universe": hypothesis.get("context", {}).get("universe", "SP500"),
            "frequency": "daily",
            "start_date": "2015-01-01",
            "end_date": "2024-12-31",
            "fields": ["price", "volume", "returns"],
        }
        if etype == ExperimentType.BACKTEST:
            data_spec.update({
                "fields": ["open", "high", "low", "close", "volume", "returns"],
                "adjustments": ["split_adjusted", "dividend_adjusted"],
            })
        return data_spec

    def _define_parameters(self, etype: ExperimentType, hypothesis: Dict[str, Any]) -> Dict[str, Any]:
        params = {"random_seed": 42, "significance_level": 0.05}
        type_params = {
            ExperimentType.BACKTEST: {
                "start_date": "2015-01-01", "end_date": "2024-12-31",
                "rebalance_frequency": "monthly", "transaction_costs_bps": 10,
            },
            ExperimentType.CROSS_VALIDATION: {
                "n_folds": 5, "split_method": "time_series", "shuffle": False,
            },
            ExperimentType.BOOTSTRAP: {
                "n_bootstrap": 1000, "block_size": 21, "method": "stationary",
            },
            ExperimentType.MONTE_CARLO: {
                "n_paths": 10000, "time_steps": 252, "distribution_type": "normal",
            },
            ExperimentType.WALK_FORWARD: {
                "training_window": 756, "testing_window": 126, "step_size": 63,
            },
            ExperimentType.SENSITIVITY: {
                "parameter_ranges": {}, "step_sizes": {}, "search_method": "grid",
            },
            ExperimentType.REGIME_ANALYSIS: {
                "n_regimes": 3, "transition_model": "markov_switching",
            },
            ExperimentType.STATISTICAL_TEST: {
                "test_type": "t_test", "tail_type": "two_tailed",
            },
            ExperimentType.SIMULATION: {
                "n_simulations": 5000, "time_horizon": 252, "model_type": "gbm",
            },
            ExperimentType.AB_TEST: {
                "sample_size": 1000, "test_duration": 126,
            },
        }
        params.update(type_params.get(etype, {}))
        return params

    def _define_metrics(self, hypothesis: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"name": "p_value", "threshold": 0.05, "direction": "less_than"},
            {"name": "effect_size", "threshold": 0.2, "direction": "greater_than"},
            {"name": "confidence_interval_width", "threshold": 0.3, "direction": "less_than"},
        ]

    def _define_success_criteria(self, hypothesis: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "primary": "p_value < 0.05 and effect_size > 0.2",
            "secondary": "out_of_sample R² > 0.02",
            "robustness": "consistent across sub-periods",
        }

    def _define_controls(self, etype: ExperimentType) -> List[Dict[str, Any]]:
        return [
            {"name": "market_beta", "type": "factor", "description": "Market risk factor"},
            {"name": "sector", "type": "categorical", "description": "Sector fixed effects"},
            {"name": "size", "type": "factor", "description": "Size factor"},
        ]

    def _define_expected_results(self, hypothesis: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "direction": "positive",
            "magnitude": "moderate",
            "significance": "expected significant at 5% level",
        }

    def run_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Mark experiment as running and simulate execution."""
        if experiment_id not in self.experiments:
            return None
        experiment = self.experiments[experiment_id]
        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = datetime.now(timezone.utc)
        return experiment.to_dict()

    def complete_experiment(self, experiment_id: str, results: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Record experiment results."""
        if experiment_id not in self.experiments:
            return None
        experiment = self.experiments[experiment_id]
        experiment.status = ExperimentStatus.COMPLETED
        experiment.completed_at = datetime.now(timezone.utc)
        experiment.actual_results = results
        return experiment.to_dict()

    def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        e = self.experiments.get(experiment_id)
        return e.to_dict() if e else None

    def list_experiments(self, status: Optional[ExperimentStatus] = None) -> List[Dict[str, Any]]:
        result = []
        for e in self.experiments.values():
            if status is None or e.status == status:
                result.append({"id": e.id, "name": e.name, "type": e.experiment_type.value, "status": e.status.value})
        return result

    def get_summary(self) -> Dict[str, Any]:
        total = len(self.experiments)
        completed = sum(1 for e in self.experiments.values() if e.status == ExperimentStatus.COMPLETED)
        return {"total_experiments": total, "completed": completed, "pending": total - completed}
