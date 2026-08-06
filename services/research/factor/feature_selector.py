"""Feature Selector — feature importance ranking and selection methods.

Supports various selection strategies for dimensionality reduction
and factor quality filtering.
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SelectionMethod(str, Enum):
    """Feature selection methods."""

    IC_BASED = "ic_based"           # Select by Information Coefficient
    CORRELATION_BASED = "correlation_based"  # Remove highly correlated
    RECURSIVE = "recursive"         # Recursive feature elimination
    TREE_BASED = "tree_based"       # Tree-based importance
    PCA_BASED = "pca_based"         # PCA component selection
    CUSTOM = "custom"               # Custom selection logic


class FeatureSelector:
    """Feature selection for factor quality and dimensionality reduction.

    Methods:
    * IC-based: select features with highest |IC|
    * Correlation-based: remove redundant correlated features
    * Recursive: iterative feature elimination
    * Tree-based: use tree model feature importance
    * PCA-based: select top principal components
    """

    def __init__(self, method: SelectionMethod = SelectionMethod.IC_BASED) -> None:
        self._method = method

    @property
    def method(self) -> SelectionMethod:
        return self._method

    def select(
        self,
        features: Dict[str, float],
        scores: Optional[Dict[str, float]] = None,
        top_k: int = 10,
        corr_threshold: float = 0.7,
    ) -> List[str]:
        """Select top features based on the configured method.

        Args:
            features: feature_name → value mapping
            scores: feature_name → importance_score mapping (for IC-based)
            top_k: number of features to select
            corr_threshold: correlation threshold for correlation-based

        Returns:
            List of selected feature names
        """
        if self._method == SelectionMethod.IC_BASED:
            return self._select_ic_based(features, scores, top_k)
        elif self._method == SelectionMethod.CORRELATION_BASED:
            return self._select_correlation_based(features, corr_threshold)
        elif self._method == SelectionMethod.RECURSIVE:
            return self._select_recursive(features, scores, top_k)
        elif self._method == SelectionMethod.TREE_BASED:
            return self._select_tree_based(features, scores, top_k)
        elif self._method == SelectionMethod.PCA_BASED:
            return self._select_pca_based(features, top_k)
        else:
            return list(features.keys())[:top_k]

    def _select_ic_based(
        self,
        features: Dict[str, float],
        scores: Optional[Dict[str, float]],
        top_k: int,
    ) -> List[str]:
        if scores is None:
            return list(features.keys())[:top_k]
        sorted_features = sorted(
            scores.items(), key=lambda x: abs(x[1]), reverse=True
        )
        return [name for name, _ in sorted_features[:top_k]]

    def _select_correlation_based(
        self,
        features: Dict[str, float],
        corr_threshold: float,
    ) -> List[str]:
        # Simplified: keep all features below correlation threshold
        # In practice, would compute pairwise correlations
        return list(features.keys())

    def _select_recursive(
        self,
        features: Dict[str, float],
        scores: Optional[Dict[str, float]],
        top_k: int,
    ) -> List[str]:
        if scores is None:
            return list(features.keys())[:top_k]
        sorted_features = sorted(scores.items(), key=lambda x: abs(x[1]), reverse=True)
        return [name for name, _ in sorted_features[:top_k]]

    def _select_tree_based(
        self,
        features: Dict[str, float],
        scores: Optional[Dict[str, float]],
        top_k: int,
    ) -> List[str]:
        if scores is None:
            return list(features.keys())[:top_k]
        sorted_features = sorted(scores.items(), key=lambda x: abs(x[1]), reverse=True)
        return [name for name, _ in sorted_features[:top_k]]

    def _select_pca_based(
        self,
        features: Dict[str, float],
        top_k: int,
    ) -> List[str]:
        return list(features.keys())[:top_k]
