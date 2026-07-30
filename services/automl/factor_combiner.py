"""Factor Combiner.

Systematic combination of multiple alpha factors using ensemble
methods: equal weight, IC-weighted, regression-based, PCA.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np


class CombineMethod(str, Enum):
    EQUAL_WEIGHT = "equal_weight"
    IC_WEIGHTED = "ic_weighted"
    REGRESSION = "regression"
    PCA = "pca"
    MAX_IC = "max_ic"


@dataclass
class CombinedFactor:
    """Result of factor combination."""

    name: str
    method: CombineMethod
    values: List[float] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=dict)
    ic: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)


class FactorCombiner:
    """Combine multiple alpha factors into a single signal.

    Supports various ensemble methods for factor blending.
    """

    def __init__(self, method: CombineMethod = CombineMethod.EQUAL_WEIGHT) -> None:
        self.method = method

    # ---- combine ----

    def combine(
        self,
        factors: Dict[str, List[float]],
        targets: Optional[List[float]] = None,
        method: Optional[CombineMethod] = None,
    ) -> CombinedFactor:
        """Combine multiple factors into one signal.

        Args:
            factors: factor_name -> values dict.
            targets: Optional target values for IC weighting.
            method: Override combine method.

        Returns:
            CombinedFactor.
        """
        m = method or self.method
        if len(factors) == 0:
            return CombinedFactor(name="empty", method=m, weights={})
        if len(factors) == 1:
            name = list(factors.keys())[0]
            vals = list(factors.values())[0]
            return CombinedFactor(
                name=name, method=m, values=vals,
                weights={name: 1.0},
            )

        if m == CombineMethod.EQUAL_WEIGHT:
            return self._equal_weight(factors)
        elif m == CombineMethod.IC_WEIGHTED:
            return self._ic_weighted(factors, targets)
        elif m == CombineMethod.REGRESSION:
            return self._regression(factors, targets)
        elif m == CombineMethod.PCA:
            return self._pca(factors)
        elif m == CombineMethod.MAX_IC:
            return self._max_ic(factors, targets)
        else:
            return self._equal_weight(factors)

    # ---- methods ----

    def _equal_weight(self, factors: Dict[str, List[float]]) -> CombinedFactor:
        n_factors = len(factors)
        w = 1.0 / n_factors
        weights = {name: w for name in factors}

        n = min(len(v) for v in factors.values())
        combined = np.zeros(n)
        for values in factors.values():
            arr = np.array(values[:n], dtype=np.float64)
            combined += np.nan_to_num(arr, nan=0.0) * w

        return CombinedFactor(
            name="equal_weight",
            method=CombineMethod.EQUAL_WEIGHT,
            values=combined.tolist(),
            weights=weights,
        )

    def _ic_weighted(
        self, factors: Dict[str, List[float]], targets: Optional[List[float]]
    ) -> CombinedFactor:
        if targets is None:
            return self._equal_weight(factors)

        # Compute IC per factor
        ics: Dict[str, float] = {}
        for name, values in factors.items():
            n = min(len(values), len(targets))
            if n < 3:
                ics[name] = 0.0
                continue
            v_arr = np.array(values[:n], dtype=np.float64)
            t_arr = np.array(targets[:n], dtype=np.float64)
            mask = ~np.isnan(v_arr) & ~np.isnan(t_arr)
            if mask.sum() < 3:
                ics[name] = 0.0
            else:
                ic = np.corrcoef(v_arr[mask], t_arr[mask])[0, 1]
                ics[name] = float(ic) if not np.isnan(ic) else 0.0

        # Weights proportional to abs(IC)
        total_abs_ic = sum(abs(v) for v in ics.values())
        if total_abs_ic == 0:
            return self._equal_weight(factors)
        weights = {name: abs(ics[name]) / total_abs_ic for name in factors}

        n = min(len(v) for v in factors.values())
        combined = np.zeros(n)
        for name, values in factors.items():
            arr = np.array(values[:n], dtype=np.float64)
            combined += np.nan_to_num(arr, nan=0.0) * weights[name]

        ic_val = float(np.corrcoef(combined, np.array(targets[:n], dtype=np.float64))[0, 1])
        return CombinedFactor(
            name="ic_weighted",
            method=CombineMethod.IC_WEIGHTED,
            values=combined.tolist(),
            weights=weights,
            ic=ic_val,
        )

    def _regression(
        self, factors: Dict[str, List[float]], targets: Optional[List[float]]
    ) -> CombinedFactor:
        if targets is None:
            return self._equal_weight(factors)

        names = sorted(factors.keys())
        n = min(*(len(v) for v in factors.values()), len(targets))

        X = np.column_stack([
            np.nan_to_num(np.array(factors[name][:n], dtype=np.float64), nan=0.0)
            for name in names
        ])
        y = np.array(targets[:n], dtype=np.float64)
        mask = ~np.isnan(y) & ~np.any(np.isnan(X), axis=1)
        if mask.sum() < 3:
            return self._equal_weight(factors)

        try:
            coeffs = np.linalg.lstsq(X[mask], y[mask], rcond=None)[0]
        except Exception:
            return self._equal_weight(factors)

        weights = {name: float(c) for name, c in zip(names, coeffs)}
        combined = np.dot(X, coeffs)

        return CombinedFactor(
            name="regression",
            method=CombineMethod.REGRESSION,
            values=combined.tolist(),
            weights=weights,
        )

    def _pca(self, factors: Dict[str, List[float]]) -> CombinedFactor:
        try:
            from sklearn.decomposition import PCA
        except ImportError:
            return self._equal_weight(factors)

        names = sorted(factors.keys())
        n = min(len(v) for v in factors.values())
        X = np.column_stack([
            np.nan_to_num(np.array(factors[name][:n], dtype=np.float64), nan=0.0)
            for name in names
        ])

        pca = PCA(n_components=1)
        combined = pca.fit_transform(X)[:, 0]
        loadings = pca.components_[0]

        # Normalize loadings to weights
        abs_load = np.abs(loadings)
        total = abs_load.sum() or 1
        weights = {name: float(abs_load[i] / total) for i, name in enumerate(names)}

        return CombinedFactor(
            name="pca",
            method=CombineMethod.PCA,
            values=combined.tolist(),
            weights=weights,
        )

    def _max_ic(
        self, factors: Dict[str, List[float]], targets: Optional[List[float]]
    ) -> CombinedFactor:
        """Return the single factor with highest IC."""
        if targets is None:
            return self._equal_weight(factors)

        best_ic = -float("inf")
        best_name = ""
        best_values: List[float] = []

        for name, values in factors.items():
            n = min(len(values), len(targets))
            v_arr = np.array(values[:n], dtype=np.float64)
            t_arr = np.array(targets[:n], dtype=np.float64)
            mask = ~np.isnan(v_arr) & ~np.isnan(t_arr)
            if mask.sum() >= 3:
                ic = np.corrcoef(v_arr[mask], t_arr[mask])[0, 1]
                if not np.isnan(ic) and ic > best_ic:
                    best_ic = float(ic)
                    best_name = name
                    best_values = values[:n]

        if not best_name:
            return self._equal_weight(factors)

        return CombinedFactor(
            name=best_name,
            method=CombineMethod.MAX_IC,
            values=best_values,
            weights={best_name: 1.0},
            ic=best_ic,
        )

    # ---- evaluation ----

    def evaluate_combination(
        self, factors: Dict[str, List[float]], targets: List[float]
    ) -> Dict[str, float]:
        """Evaluate all combine methods and return comparison."""
        results: Dict[str, float] = {}
        for method in CombineMethod:
            combined = self.combine(factors, targets, method)
            n = min(len(combined.values), len(targets))
            c_arr = np.array(combined.values[:n], dtype=np.float64)
            t_arr = np.array(targets[:n], dtype=np.float64)
            mask = ~np.isnan(c_arr) & ~np.isnan(t_arr)
            if mask.sum() >= 3:
                ic = np.corrcoef(c_arr[mask], t_arr[mask])[0, 1]
                results[method.value] = float(ic) if not np.isnan(ic) else 0.0
            else:
                results[method.value] = 0.0
        return results
