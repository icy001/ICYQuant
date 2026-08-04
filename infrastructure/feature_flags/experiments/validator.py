"""
Experiment validation.

Validates experiment configurations
including variants, traffic allocation,
and statistical parameters.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .experiment import Experiment
from .variant import Variant


class ExperimentValidator:
    """Validator for experiment configurations."""

    def validate_variant(self, variant: Variant) -> List[str]:
        errors = []
        if not variant.variant_id:
            errors.append("variant_id is required")
        if variant.weight < 0:
            errors.append(f"Weight must be >= 0, got {variant.weight}")
        return errors

    def validate_variants(self, variants: List[Variant]) -> List[str]:
        errors = []
        if len(variants) < 2:
            errors.append("At least 2 variants required")
        for v in variants:
            errors.extend(self.validate_variant(v))
        # Check unique IDs
        ids = [v.variant_id for v in variants]
        if len(ids) != len(set(ids)):
            errors.append("Variant IDs must be unique")
        # Check for control
        has_control = any(v.is_control for v in variants)
        if not has_control:
            errors.append("At least one variant must be control")
        # Check total weight
        total_weight = sum(v.weight for v in variants)
        if total_weight <= 0:
            errors.append("Total variant weight must be > 0")
        return errors

    def validate_experiment(self, experiment: Experiment) -> List[str]:
        errors = []
        if not experiment.experiment_id:
            errors.append("experiment_id is required")
        if not experiment.feature_key:
            errors.append("feature_key is required")
        variant_errors = self.validate_variants(experiment.variants)
        errors.extend(variant_errors)
        if not 0 < experiment.traffic_percentage <= 100:
            errors.append(
                f"Traffic percentage must be 1-100, got {experiment.traffic_percentage}"
            )
        return errors
