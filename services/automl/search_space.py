"""AutoML Search Space.

Unified definition of model, feature, and hyperparameter search
space for automated model selection and tuning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import numpy as np


class ParamType(str, Enum):
    CATEGORICAL = "categorical"
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"


@dataclass
class CategoricalParam:
    name: str
    choices: List[Any]
    default: Any = None

    def sample(self, rng: Optional[np.random.RandomState] = None) -> Any:
        rng = rng or np.random
        return rng.choice(self.choices)

    def __repr__(self) -> str:
        return f"CategoricalParam({self.name}, choices={self.choices})"


@dataclass
class ContinuousParam:
    name: str
    low: float
    high: float
    log_scale: bool = False
    default: Optional[float] = None

    def sample(self, rng: Optional[np.random.RandomState] = None) -> float:
        rng = rng or np.random
        if self.log_scale:
            lo = np.log(self.low)
            hi = np.log(self.high)
            return float(np.exp(rng.uniform(lo, hi)))
        return float(rng.uniform(self.low, self.high))

    def __repr__(self) -> str:
        return f"ContinuousParam({self.name}, [{self.low}, {self.high}])"


@dataclass
class DiscreteParam:
    name: str
    low: int
    high: int
    step: int = 1
    default: Optional[int] = None

    def sample(self, rng: Optional[np.random.RandomState] = None) -> int:
        rng = rng or np.random
        n = (self.high - self.low) // self.step + 1
        return int(self.low + rng.randint(0, n) * self.step)

    @property
    def values(self) -> List[int]:
        return list(range(self.low, self.high + 1, self.step))

    def __repr__(self) -> str:
        return f"DiscreteParam({self.name}, [{self.low}, {self.high}], step={self.step})"


ParamDef = Union[CategoricalParam, ContinuousParam, DiscreteParam]


@dataclass
class ModelConfig:
    """Configuration for a model type in the search space."""

    name: str
    module: str = ""  # e.g. "lightgbm", "xgboost"
    params: List[ParamDef] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    def sample_params(self, rng: Optional[np.random.RandomState] = None) -> Dict[str, Any]:
        return {p.name: p.sample(rng) for p in self.params}


@dataclass
class SearchSpace:
    """Complete AutoML search space.

    Defines:
        - feature_universe: available feature names and groups
        - model_candidates: model types to try
        - hyperparams: shared hyperparameters
        - constraints: search constraints
    """

    name: str = "default"
    feature_universe: List[str] = field(default_factory=list)
    feature_groups: Dict[str, List[str]] = field(default_factory=dict)
    model_candidates: List[ModelConfig] = field(default_factory=list)
    hyperparams: List[ParamDef] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    max_trials: int = 100
    timeout_seconds: int = 3600

    def add_model(self, name: str, module: str = "", params: Optional[List[ParamDef]] = None) -> ModelConfig:
        mc = ModelConfig(name=name, module=module, params=params or [])
        self.model_candidates.append(mc)
        return mc

    def add_param(self, param: ParamDef) -> None:
        self.hyperparams.append(param)

    def add_feature_group(self, name: str, features: List[str]) -> None:
        self.feature_groups[name] = features
        self.feature_universe.extend(features)
        self.feature_universe = sorted(set(self.feature_universe))

    def sample_config(self, rng: Optional[np.random.RandomState] = None) -> Dict[str, Any]:
        rng = rng or np.random
        model = rng.choice(self.model_candidates)
        config: Dict[str, Any] = {
            "model": model.name,
            "module": model.module,
            "params": model.sample_params(rng),
        }
        for p in self.hyperparams:
            config["params"][p.name] = p.sample(rng)
        return config

    def grid_configs(self) -> List[Dict[str, Any]]:
        """Generate all configs from grid (for discrete/categorical only)."""
        configs: List[Dict[str, Any]] = []
        for model in self.model_candidates:
            param_lists = []
            for p in model.params:
                if isinstance(p, CategoricalParam):
                    param_lists.append([(p.name, v) for v in p.choices])
                elif isinstance(p, DiscreteParam):
                    param_lists.append([(p.name, v) for v in p.values])
            for p in self.hyperparams:
                if isinstance(p, CategoricalParam):
                    param_lists.append([(p.name, v) for v in p.choices])
                elif isinstance(p, DiscreteParam):
                    param_lists.append([(p.name, v) for v in p.values])

            if not param_lists:
                configs.append({"model": model.name, "module": model.module, "params": {}})
                continue

            from itertools import product
            for combo in product(*param_lists):
                configs.append({
                    "model": model.name,
                    "module": model.module,
                    "params": dict(combo),
                })
        return configs

    def summary(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "features": len(self.feature_universe),
            "feature_groups": len(self.feature_groups),
            "model_candidates": [m.name for m in self.model_candidates],
            "hyperparams": len(self.hyperparams),
            "max_trials": self.max_trials,
        }
