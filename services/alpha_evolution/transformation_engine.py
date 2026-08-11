"""
Transformation Engine — Applies mathematical/numerical transformations to factor expressions.

Supported transformations:
    - Normalization (zscore, rank, percentile, winsorize)
    - Nonlinear (log, sqrt, power, exponential)
    - Rolling (mean, std, min, max, median, skew, kurtosis)
    - Delta (difference, percent change)
    - Cross-sectional (cs_rank, cs_zscore, group_mean)
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from services.alpha_evolution.genome import Genome, ExpressionType
from services.alpha_evolution.gene import Gene, GeneFunction, GeneType


class TransformCategory(Enum):
    NORMALIZATION = "normalization"
    NONLINEAR = "nonlinear"
    ROLLING = "rolling"
    DELTA = "delta"
    CROSS_SECTIONAL = "cross_sectional"
    CONDITIONAL = "conditional"


_TRANSFORM_REGISTRY: Dict[str, Dict[str, Any]] = {
    # Normalization
    GeneFunction.ZSCORE: {
        "category": TransformCategory.NORMALIZATION,
        "params": ["window"],
        "default_window": 252,
    },
    GeneFunction.RANK: {
        "category": TransformCategory.NORMALIZATION,
        "params": [],
    },
    GeneFunction.PERCENTILE: {
        "category": TransformCategory.NORMALIZATION,
        "params": [],
    },
    GeneFunction.WINSORIZE: {
        "category": TransformCategory.NORMALIZATION,
        "params": ["lower", "upper"],
        "default_lower": 0.01,
        "default_upper": 0.99,
    },
    GeneFunction.NEUTRALIZE: {
        "category": TransformCategory.NORMALIZATION,
        "params": ["by"],
    },
    # Nonlinear
    GeneFunction.LOG: {"category": TransformCategory.NONLINEAR, "params": []},
    GeneFunction.SQRT: {"category": TransformCategory.NONLINEAR, "params": []},
    GeneFunction.ABS: {"category": TransformCategory.NONLINEAR, "params": []},
    GeneFunction.SIGN: {"category": TransformCategory.NONLINEAR, "params": []},
    # Rolling
    GeneFunction.MEAN: {
        "category": TransformCategory.ROLLING,
        "params": ["window"],
        "default_window": 20,
    },
    GeneFunction.STD: {
        "category": TransformCategory.ROLLING,
        "params": ["window"],
        "default_window": 20,
    },
    GeneFunction.MIN: {
        "category": TransformCategory.ROLLING,
        "params": ["window"],
        "default_window": 20,
    },
    GeneFunction.MAX: {
        "category": TransformCategory.ROLLING,
        "params": ["window"],
        "default_window": 20,
    },
    GeneFunction.SUM: {
        "category": TransformCategory.ROLLING,
        "params": ["window"],
        "default_window": 20,
    },
    GeneFunction.MEDIAN: {
        "category": TransformCategory.ROLLING,
        "params": ["window"],
        "default_window": 20,
    },
    GeneFunction.SKEW: {
        "category": TransformCategory.ROLLING,
        "params": ["window"],
        "default_window": 60,
    },
    GeneFunction.KURTOSIS: {
        "category": TransformCategory.ROLLING,
        "params": ["window"],
        "default_window": 60,
    },
    # Delta
    GeneFunction.ROC: {
        "category": TransformCategory.DELTA,
        "params": ["period"],
        "default_period": 1,
    },
    # Cross-sectional
    GeneFunction.CROSS_SECTIONAL_RANK: {
        "category": TransformCategory.CROSS_SECTIONAL,
        "params": [],
    },
    GeneFunction.CROSS_SECTIONAL_ZSCORE: {
        "category": TransformCategory.CROSS_SECTIONAL,
        "params": [],
    },
    GeneFunction.GROUP_MEAN: {
        "category": TransformCategory.CROSS_SECTIONAL,
        "params": ["group_by"],
    },
    GeneFunction.GROUP_MEDIAN: {
        "category": TransformCategory.CROSS_SECTIONAL,
        "params": ["group_by"],
    },
    # Conditional
    GeneFunction.IF_ELSE: {
        "category": TransformCategory.CONDITIONAL,
        "params": [],
    },
    GeneFunction.CLIP: {
        "category": TransformCategory.CONDITIONAL,
        "params": ["lower", "upper"],
    },
    # Decay
    GeneFunction.DECAY_LINEAR: {
        "category": TransformCategory.ROLLING,
        "params": ["window"],
        "default_window": 20,
    },
    GeneFunction.DECAY_EXP: {
        "category": TransformCategory.ROLLING,
        "params": ["window", "half_life"],
        "default_window": 20,
        "default_half_life": 5,
    },
}


class TransformationEngine:
    """
    Engine for applying transformations to factor expressions.

    Operations:
        - Apply a specific transformation to a genome
        - Chain multiple transformations
        - Validate transformation compatibility
        - Wrap/unwrap transformations
    """

    @staticmethod
    def apply_transform(
        genome: Genome,
        transform_name: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Genome:
        """Apply a transformation to a genome."""
        if transform_name not in _TRANSFORM_REGISTRY:
            raise ValueError(f"Unknown transformation: {transform_name}")

        if not genome.root_gene:
            return genome

        config = _TRANSFORM_REGISTRY[transform_name]
        merged_params = {}

        # Apply defaults
        for key, default_val in config.items():
            if key.startswith("default_"):
                param_name = key.replace("default_", "")
                merged_params[param_name] = default_val

        # Override with provided params
        if params:
            merged_params.update(params)

        genome.root_gene = Gene.function(
            transform_name, genome.root_gene, **merged_params
        )
        genome.version += 1
        return genome

    @staticmethod
    def apply_chain(
        genome: Genome,
        transforms: List[tuple[str, Optional[Dict[str, Any]]]],
    ) -> Genome:
        """Apply a chain of transformations in sequence."""
        for transform_name, params in transforms:
            TransformationEngine.apply_transform(genome, transform_name, params)
        return genome

    @staticmethod
    def strip_transform(
        genome: Genome, transform_name: str
    ) -> Optional[Genome]:
        """Remove the outermost transformation if it matches."""
        if not genome.root_gene:
            return None
        if (
            genome.root_gene.type == GeneType.FUNCTION
            and genome.root_gene.value == transform_name
            and genome.root_gene.children
        ):
            genome.root_gene = genome.root_gene.children[0]
            genome.version += 1
            return genome
        return None

    @staticmethod
    def normalize(
        genome: Genome,
        method: str = "zscore",
        window: int = 252,
    ) -> Genome:
        """Apply standard normalization."""
        params = {"window": window} if method in (GeneFunction.ZSCORE,) else {}
        return TransformationEngine.apply_transform(genome, method, params)

    @staticmethod
    def cross_sectionalize(genome: Genome) -> Genome:
        """Wrap genome in cross-sectional rank."""
        return TransformationEngine.apply_transform(
            genome, GeneFunction.CROSS_SECTIONAL_RANK
        )

    @staticmethod
    def get_available_transforms(
        category: Optional[TransformCategory] = None,
    ) -> List[str]:
        """List available transformations, optionally filtered by category."""
        if category is None:
            return list(_TRANSFORM_REGISTRY.keys())
        return [
            name
            for name, config in _TRANSFORM_REGISTRY.items()
            if config.get("category") == category
        ]

    @staticmethod
    def get_transform_info(transform_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific transformation."""
        return _TRANSFORM_REGISTRY.get(transform_name)
