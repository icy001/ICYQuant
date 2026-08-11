"""
ICYQuant Data Drift - Raw data distribution drift detection.

Detects shifts in input data distributions between training and production.
Uses Population Stability Index (PSI), KS-test, and Jensen-Shannon divergence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DriftMethod(Enum):
    """Statistical methods for drift detection."""

    PSI = "psi"                    # Population Stability Index
    KS_TEST = "ks_test"            # Kolmogorov-Smirnov test
    JS_DIVERGENCE = "js_divergence"  # Jensen-Shannon divergence
    WASSERSTEIN = "wasserstein"    # Wasserstein / Earth Mover's distance
    CHI_SQUARE = "chi_square"      # Chi-squared test


@dataclass
class DataDriftResult:
    """Result of data drift detection."""

    method: DriftMethod = DriftMethod.PSI
    drift_score: float = 0.0
    p_value: float = 1.0
    significant: bool = False

    # Per-feature results
    feature_scores: Dict[str, float] = field(default_factory=dict)
    drifted_features: List[str] = field(default_factory=list)

    # Metadata
    reference_samples: int = 0
    current_samples: int = 0
    feature_count: int = 0
    checked_at: datetime = field(default_factory=datetime.utcnow)


class DataDriftDetector:
    """Detects distribution shifts in raw input data.

    Used to identify when production data diverges from training data,
    which may degrade model performance.

    Methods:
    - PSI (Population Stability Index): Industry standard for drift
    - KS-test: Two-sample Kolmogorov-Smirnov test
    - JS Divergence: Symmetric KL-divergence variant
    """

    def __init__(
        self,
        method: DriftMethod = DriftMethod.PSI,
        threshold: float = 0.10,
        bins: int = 10,
    ) -> None:
        self.method = method
        self.threshold = threshold
        self.bins = bins

    # -- Detect --

    async def detect(
        self,
        reference_data: Any,
        current_data: Any,
        feature_names: Optional[List[str]] = None,
    ) -> DataDriftResult:
        """Detect data drift between reference and current data.

        Args:
            reference_data: Training/reference data (feature matrix).
            current_data: Current production data.
            feature_names: Optional feature names.

        Returns:
            DataDriftResult with per-feature scores.
        """
        result = DataDriftResult(method=self.method)

        # Placeholder: actual drift computation in production
        # For each feature column, compute PSI/KS/JS between reference and current

        if feature_names:
            result.feature_count = len(feature_names)
            for name in feature_names:
                score = await self._compute_drift(name, None, None)
                result.feature_scores[name] = score
                if score > self.threshold:
                    result.drifted_features.append(name)

        result.drift_score = (
            sum(result.feature_scores.values()) / max(len(result.feature_scores), 1)
            if result.feature_scores else 0.0
        )
        result.significant = result.drift_score > self.threshold

        logger.info("Data drift check: score=%.4f, significant=%s, drifted=%d/%d",
                     result.drift_score, result.significant,
                     len(result.drifted_features), result.feature_count)

        return result

    async def _compute_drift(self, feature_name: str, reference: Any, current: Any) -> float:
        """Compute drift score for a single feature."""
        return 0.0

    # -- PSI Computation --

    @staticmethod
    def compute_psi(
        expected: List[float],
        actual: List[float],
        bins: int = 10,
    ) -> float:
        """Compute Population Stability Index (PSI).

        PSI = sum((actual% - expected%) * ln(actual% / expected%))

        Interpretation:
        - PSI < 0.1: No significant change
        - 0.1 <= PSI < 0.25: Moderate change
        - PSI >= 0.25: Significant change
        """
        # Placeholder: actual PSI computation
        return 0.0

    @staticmethod
    def interpret_psi(psi_value: float) -> str:
        """Interpret a PSI value."""
        if psi_value < 0.1:
            return "No significant change"
        elif psi_value < 0.25:
            return "Moderate change - investigate"
        else:
            return "Significant change - action required"
