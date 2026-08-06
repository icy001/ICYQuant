"""Research Validator — validation rules for research platform entities.

Ensures experiments, datasets, and related entities meet schema
and business-rule requirements before persistence or execution.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when a research entity fails validation."""

    def __init__(self, errors: List[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors))


class ResearchValidator:
    """Validates research platform entities against schema and business rules.

    Validation domains:
    * Experiment — name, config, dataset reference
    * Dataset — name, source, schema completeness
    * Run — experiment reference, config
    * Artifact — type, path, experiment reference
    """

    # ── experiment validation ─────────────────────────────────────────────

    @staticmethod
    def validate_experiment(data: Dict[str, Any]) -> List[str]:
        """Validate an experiment entity. Returns list of error messages."""
        errors: List[str] = []

        if not data.get("name"):
            errors.append("Experiment name is required")
        elif len(data["name"]) > 256:
            errors.append("Experiment name must be <= 256 characters")

        if "config" in data and not isinstance(data.get("config"), dict):
            errors.append("Experiment config must be a dictionary")

        if "tags" in data and not isinstance(data.get("tags"), list):
            errors.append("Experiment tags must be a list")

        if "metadata" in data and not isinstance(data.get("metadata"), dict):
            errors.append("Experiment metadata must be a dictionary")

        return errors

    @staticmethod
    def validate_experiment_create(data: Dict[str, Any]) -> None:
        """Validate and raise on experiment creation errors."""
        errors = ResearchValidator.validate_experiment(data)
        if errors:
            raise ValidationError(errors)

    # ── dataset validation ────────────────────────────────────────────────

    @staticmethod
    def validate_dataset(data: Dict[str, Any]) -> List[str]:
        """Validate a dataset entity."""
        errors: List[str] = []

        if not data.get("name"):
            errors.append("Dataset name is required")
        elif len(data["name"]) > 256:
            errors.append("Dataset name must be <= 256 characters")

        if not data.get("source"):
            errors.append("Dataset source is required")

        if "schema" in data and not isinstance(data.get("schema"), dict):
            errors.append("Dataset schema must be a dictionary")

        if "tags" in data and not isinstance(data.get("tags"), list):
            errors.append("Dataset tags must be a list")

        return errors

    @staticmethod
    def validate_dataset_create(data: Dict[str, Any]) -> None:
        """Validate and raise on dataset creation errors."""
        errors = ResearchValidator.validate_dataset(data)
        if errors:
            raise ValidationError(errors)

    # ── run validation ────────────────────────────────────────────────────

    @staticmethod
    def validate_run(data: Dict[str, Any]) -> List[str]:
        """Validate a run entity."""
        errors: List[str] = []

        if not data.get("experiment_id"):
            errors.append("Run experiment_id is required")

        if "config" in data and not isinstance(data.get("config"), dict):
            errors.append("Run config must be a dictionary")

        return errors

    @staticmethod
    def validate_run_create(data: Dict[str, Any]) -> None:
        """Validate and raise on run creation errors."""
        errors = ResearchValidator.validate_run(data)
        if errors:
            raise ValidationError(errors)

    # ── artifact validation ───────────────────────────────────────────────

    @staticmethod
    def validate_artifact(data: Dict[str, Any]) -> List[str]:
        """Validate an artifact entity."""
        errors: List[str] = []

        if not data.get("experiment_id"):
            errors.append("Artifact experiment_id is required")
        if not data.get("name"):
            errors.append("Artifact name is required")
        if not data.get("type"):
            errors.append("Artifact type is required")

        return errors

    @staticmethod
    def validate_artifact_create(data: Dict[str, Any]) -> None:
        """Validate and raise on artifact creation errors."""
        errors = ResearchValidator.validate_artifact(data)
        if errors:
            raise ValidationError(errors)

    # ── config validation ─────────────────────────────────────────────────

    @staticmethod
    def validate_config(data: Dict[str, Any], required_keys: Optional[List[str]] = None) -> List[str]:
        """Validate a configuration dictionary against required keys."""
        errors: List[str] = []
        if required_keys:
            for key in required_keys:
                if key not in data:
                    errors.append(f"Config missing required key: {key}")
        return errors


# Convenience aliases matching the __init__.py export names
validate_research = ResearchValidator.validate_experiment
validate_dataset = ResearchValidator.validate_dataset
validate_run = ResearchValidator.validate_run
validate_artifact = ResearchValidator.validate_artifact
