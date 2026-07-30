"""Feature Importance Analyzer.

Post-training analysis of feature contributions to model predictions.
Supports multiple importance computation methods and produces ranked
reports for feature pruning and model interpretation.

Usage::

    from services.feature_engineering import FeatureImportanceAnalyzer

    analyzer = FeatureImportanceAnalyzer()
    report = analyzer.analyze(model, X_train, y_train, feature_names)
    print(report.top_features(10))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class ImportanceMethod(str, Enum):
    """Method for computing feature importance."""

    TREE_GAIN = "tree_gain"            # tree-based gain importance
    TREE_SPLIT = "tree_split"          # tree-based split count
    PERMUTATION = "permutation"        # permutation importance
    SHAP = "shap"                      # SHAP values (if available)
    COEFFICIENT = "coefficient"        # linear model coefficients
    CORRELATION = "correlation"        # absolute correlation with target


@dataclass
class ImportanceReport:
    """Structured feature importance report.

    Attributes:
        importances: Dict mapping feature_name -> importance_score.
        method: Method used for computation.
        ranked_features: Features sorted by importance descending.
        metadata: Additional diagnostic information.
    """

    importances: Dict[str, float]
    method: ImportanceMethod
    ranked_features: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.ranked_features:
            self.ranked_features = sorted(
                self.importances,
                key=lambda f: self.importances[f],
                reverse=True,
            )

    def top_features(self, n: int = 10) -> List[Tuple[str, float]]:
        """Return top-n (feature_name, importance) pairs."""
        return [(f, self.importances[f]) for f in self.ranked_features[:n]]

    def cumulative_importance(self, n: int = -1) -> float:
        """Sum of importance for top-n features."""
        if n <= 0:
            n = len(self.ranked_features)
        return sum(self.importances[f] for f in self.ranked_features[:n])

    def prune_threshold(self, min_importance: float) -> List[str]:
        """Return features with importance >= min_importance."""
        return [f for f in self.ranked_features if self.importances[f] >= min_importance]

    def __repr__(self) -> str:
        return (
            f"ImportanceReport(method={self.method.value}, "
            f"n_features={len(self.importances)})"
        )


class FeatureImportanceAnalyzer:
    """Compute and report feature importance from a trained model.

    Example::

        analyzer = FeatureImportanceAnalyzer()
        report = analyzer.analyze(model, X_train, y_train, feature_names)
        for name, score in report.top_features(10):
            print(f"  {name}: {score:.4f}")
    """

    def analyze(
        self,
        model: Any,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        method: ImportanceMethod = ImportanceMethod.TREE_GAIN,
        n_repeats: int = 5,
    ) -> ImportanceReport:
        """Compute feature importance.

        Args:
            model: Trained model with feature_importances_, coef_, or predict.
            X: Feature matrix (n_samples, n_features).
            y: Target values.
            feature_names: List of feature names.
            method: Importance computation method.
            n_repeats: Number of repeats for permutation importance.

        Returns:
            ImportanceReport with ranked features.
        """
        if method == ImportanceMethod.TREE_GAIN:
            importances = self._tree_gain_importance(model, feature_names)
        elif method == ImportanceMethod.TREE_SPLIT:
            importances = self._tree_split_importance(model, feature_names)
        elif method == ImportanceMethod.PERMUTATION:
            importances = self._permutation_importance(model, X, y, feature_names, n_repeats)
        elif method == ImportanceMethod.SHAP:
            importances = self._shap_importance(model, X, feature_names)
        elif method == ImportanceMethod.COEFFICIENT:
            importances = self._coefficient_importance(model, feature_names)
        elif method == ImportanceMethod.CORRELATION:
            importances = self._correlation_importance(X, y, feature_names)
        else:
            importances = {}

        # Normalize to sum to 1
        total = sum(importances.values())
        if total > 0:
            importances = {k: v / total for k, v in importances.items()}

        return ImportanceReport(
            importances=importances,
            method=method,
            metadata={"n_features": len(feature_names), "n_samples": X.shape[0]},
        )

    # ---- internal methods ----

    def _tree_gain_importance(self, model: Any, feature_names: List[str]) -> Dict[str, float]:
        """Extract gain-based importance from tree models."""
        if hasattr(model, "feature_importances_"):
            scores = model.feature_importances_
            return {feature_names[i]: float(scores[i]) for i in range(len(feature_names))}
        return {}

    def _tree_split_importance(self, model: Any, feature_names: List[str]) -> Dict[str, float]:
        """Extract split-count importance from tree models."""
        # For sklearn trees, feature_importances_ is gain-based by default
        # Split count is not directly exposed; fall back to gain
        return self._tree_gain_importance(model, feature_names)

    def _permutation_importance(
        self,
        model: Any,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: List[str],
        n_repeats: int = 5,
    ) -> Dict[str, float]:
        """Compute permutation importance.

        Importance = decrease in model score when a feature is randomly shuffled.
        """
        from sklearn.metrics import mean_squared_error, accuracy_score

        X_clean = np.nan_to_num(X, nan=0.0)
        y_clean = np.nan_to_num(y, nan=0.0)

        # Determine task type
        if len(np.unique(y_clean)) <= 10:
            baseline_preds = model.predict(X_clean)
            baseline_score = accuracy_score(y_clean, baseline_preds)
            scorer = accuracy_score
            is_classification = True
        else:
            baseline_preds = model.predict(X_clean)
            baseline_score = -mean_squared_error(y_clean, baseline_preds)
            scorer = lambda yt, yp: -mean_squared_error(yt, yp)  # noqa: E731
            is_classification = False

        importances: Dict[str, float] = {}
        rng = np.random.RandomState(42)

        for i, name in enumerate(feature_names):
            scores: List[float] = []
            for _ in range(n_repeats):
                X_permuted = X_clean.copy()
                rng.shuffle(X_permuted[:, i])
                preds = model.predict(X_permuted)
                if is_classification:
                    scores.append(scorer(y_clean, preds))
                else:
                    scores.append(scorer(y_clean, preds))
            # Importance = drop in performance
            avg_score = float(np.mean(scores))
            importances[name] = max(0.0, baseline_score - avg_score)

        return importances

    def _shap_importance(self, model: Any, X: np.ndarray, feature_names: List[str]) -> Dict[str, float]:
        """Compute SHAP-based feature importance.

        Uses shap.TreeExplainer or shap.KernelExplainer if available.
        """
        try:
            import shap
        except ImportError:
            return {}

        X_sample = X[: min(100, X.shape[0])]
        X_sample = np.nan_to_num(X_sample, nan=0.0)

        try:
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X_sample)
        except Exception:
            try:
                explainer = shap.KernelExplainer(model.predict, X_sample[:10])
                shap_values = explainer.shap_values(X_sample[:10])
            except Exception:
                return {}

        if isinstance(shap_values, list):
            shap_values = shap_values[0]  # for classification, take class 0

        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        return {feature_names[i]: float(mean_abs_shap[i]) for i in range(len(feature_names))}

    def _coefficient_importance(self, model: Any, feature_names: List[str]) -> Dict[str, float]:
        """Extract importance from linear model coefficients."""
        if hasattr(model, "coef_"):
            coef = np.array(model.coef_).ravel()
            return {feature_names[i]: float(abs(coef[i])) for i in range(len(feature_names))}
        return {}

    def _correlation_importance(
        self, X: np.ndarray, y: np.ndarray, feature_names: List[str]
    ) -> Dict[str, float]:
        """Compute absolute Pearson correlation with target."""
        importances: Dict[str, float] = {}
        for i, name in enumerate(feature_names):
            col = X[:, i]
            mask = ~np.isnan(col) & ~np.isnan(y)
            if mask.sum() >= 3:
                corr = np.corrcoef(col[mask], y[mask])[0, 1]
                importances[name] = float(abs(corr))
            else:
                importances[name] = 0.0
        return importances
