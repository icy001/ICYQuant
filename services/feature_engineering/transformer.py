"""Feature Transformers.

Standardized transformations for feature engineering:
    - Normalization (min-max scaling)
    - Standardization (z-score)
    - Log transform
    - Rank transform
    - Clipping
    - Winsorization

Usage::

    from services.feature_engineering import StandardizeTransformer

    t = StandardizeTransformer()
    result = t.transform([1.0, 2.0, 3.0, 4.0, 5.0])
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class TransformResult:
    """Output of a transformation."""

    values: List[float]
    params: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        n = len(self.values)
        return f"TransformResult(n={n}, params={list(self.params.keys())})"


@dataclass
class TransformContext:
    """Optional context for stateful transformations (e.g. fit params)."""

    params: Dict[str, Any] = field(default_factory=dict)
    fit_values: Optional[List[float]] = None


# ---- base ----

class BaseTransformer:
    """Abstract base for all feature transformers."""

    name: str = "base"

    def fit(self, values: List[float]) -> TransformContext:
        """Learn transformation parameters from data."""
        return TransformContext()

    def transform(self, values: List[float], ctx: Optional[TransformContext] = None) -> TransformResult:
        """Apply the transformation."""
        raise NotImplementedError

    def fit_transform(self, values: List[float]) -> TransformResult:
        """Fit and transform in one call."""
        ctx = self.fit(values)
        return self.transform(values, ctx)

    def inverse_transform(self, values: List[float], ctx: TransformContext) -> List[float]:
        """Reverse the transformation (if possible)."""
        raise NotImplementedError(f"{self.name} does not support inverse transform")


# ---- Normalization (Min-Max) ----

class NormalizeTransformer(BaseTransformer):
    """Min-max normalization: scale values to [0, 1] or custom range.

    Args:
        feature_range: Target (min, max) tuple.
        clip: Whether to clip output to feature_range.
    """

    name = "normalize"

    def __init__(self, feature_range: Tuple[float, float] = (0.0, 1.0), clip: bool = True) -> None:
        self.feature_range = feature_range
        self.clip = clip

    def fit(self, values: List[float]) -> TransformContext:
        arr = np.array([v for v in values if v is not None and not np.isnan(v)], dtype=np.float64)
        if len(arr) == 0:
            return TransformContext(params={"min": 0.0, "max": 1.0, "scale": 1.0})
        return TransformContext(params={
            "min": float(arr.min()),
            "max": float(arr.max()),
            "scale": float(arr.max() - arr.min()),
        })

    def transform(self, values: List[float], ctx: Optional[TransformContext] = None) -> TransformResult:
        if ctx is None:
            ctx = TransformContext(params={"min": 0.0, "max": 1.0, "scale": 1.0})
        vmin = ctx.params.get("min", 0.0)
        vmax = ctx.params.get("max", 1.0)
        scale = ctx.params.get("scale", 1.0)
        rmin, rmax = self.feature_range

        if scale == 0:
            return TransformResult(values=[rmin] * len(values), params=ctx.params)

        result: List[float] = []
        for v in values:
            if v is None or (isinstance(v, float) and np.isnan(v)):
                result.append(float("nan"))
            else:
                scaled = (float(v) - vmin) / scale * (rmax - rmin) + rmin
                if self.clip:
                    scaled = max(rmin, min(rmax, scaled))
                result.append(scaled)
        return TransformResult(values=result, params=ctx.params)

    def inverse_transform(self, values: List[float], ctx: TransformContext) -> List[float]:
        vmin = ctx.params.get("min", 0.0)
        vmax = ctx.params.get("max", 1.0)
        scale = ctx.params.get("scale", 1.0)
        rmin, rmax = self.feature_range
        if scale == 0:
            return [vmin] * len(values)
        return [(v - rmin) / (rmax - rmin) * scale + vmin for v in values]


# ---- Standardization (Z-score) ----

class StandardizeTransformer(BaseTransformer):
    """Z-score standardization: (x - mean) / std.

    Args:
        with_mean: Center data to zero mean.
        with_std: Scale to unit variance.
    """

    name = "standardize"

    def __init__(self, with_mean: bool = True, with_std: bool = True) -> None:
        self.with_mean = with_mean
        self.with_std = with_std

    def fit(self, values: List[float]) -> TransformContext:
        arr = np.array([v for v in values if v is not None and not np.isnan(v)], dtype=np.float64)
        if len(arr) == 0:
            return TransformContext(params={"mean": 0.0, "std": 1.0})
        return TransformContext(params={
            "mean": float(arr.mean()),
            "std": float(arr.std(ddof=0)) if len(arr) > 1 else 1.0,
        })

    def transform(self, values: List[float], ctx: Optional[TransformContext] = None) -> TransformResult:
        if ctx is None:
            ctx = TransformContext(params={"mean": 0.0, "std": 1.0})
        mean = ctx.params.get("mean", 0.0)
        std = ctx.params.get("std", 1.0)

        warnings: List[str] = []
        if std == 0:
            warnings.append("std is zero; returning zeros")
            return TransformResult(values=[0.0] * len(values), params=ctx.params, warnings=warnings)

        result: List[float] = []
        for v in values:
            if v is None or (isinstance(v, float) and np.isnan(v)):
                result.append(float("nan"))
            else:
                val = float(v)
                if self.with_mean:
                    val -= mean
                if self.with_std:
                    val /= std
                result.append(val)
        return TransformResult(values=result, params=ctx.params, warnings=warnings)

    def inverse_transform(self, values: List[float], ctx: TransformContext) -> List[float]:
        mean = ctx.params.get("mean", 0.0)
        std = ctx.params.get("std", 1.0)
        return [v * std + mean for v in values]


# ---- Log Transform ----

class LogTransformer(BaseTransformer):
    """Logarithmic transform: log(x + offset).

    Args:
        base: Logarithm base (default: natural log).
        offset: Offset added before log to handle zeros/negatives.
    """

    name = "log"

    def __init__(self, base: float = math.e, offset: float = 1.0) -> None:
        self.base = base
        self.offset = offset

    def fit(self, values: List[float]) -> TransformContext:
        return TransformContext(params={"offset": self.offset, "base": self.base})

    def transform(self, values: List[float], ctx: Optional[TransformContext] = None) -> TransformResult:
        offset = self.offset
        base = self.base
        if ctx:
            offset = ctx.params.get("offset", offset)
            base = ctx.params.get("base", base)

        result: List[float] = []
        for v in values:
            if v is None or (isinstance(v, float) and np.isnan(v)):
                result.append(float("nan"))
            else:
                val = float(v) + offset
                if val <= 0:
                    result.append(float("nan"))
                elif base == math.e:
                    result.append(math.log(val))
                else:
                    result.append(math.log(val) / math.log(base))
        return TransformResult(values=result, params={"offset": offset, "base": base})

    def inverse_transform(self, values: List[float], ctx: TransformContext) -> List[float]:
        offset = ctx.params.get("offset", self.offset)
        base = ctx.params.get("base", self.base)
        if base == math.e:
            return [math.exp(v) - offset for v in values]
        return [base ** v - offset for v in values]


# ---- Rank Transform ----

class RankTransformer(BaseTransformer):
    """Rank-based transformation: replace values with their percentile rank.

    Args:
        method: "average", "min", "max", "dense" ranking method.
        normalize: If True, output ranks in [0, 1].
    """

    name = "rank"

    def __init__(self, method: str = "average", normalize: bool = True) -> None:
        self.method = method
        self.normalize = normalize

    def fit(self, values: List[float]) -> TransformContext:
        arr = np.array([v for v in values if v is not None and not np.isnan(v)], dtype=np.float64)
        return TransformContext(params={"n": len(arr)})

    def transform(self, values: List[float], ctx: Optional[TransformContext] = None) -> TransformResult:
        arr = np.array(values, dtype=np.float64)
        nan_mask = np.isnan(arr)

        # Rank the non-NaN values
        clean_idx = np.where(~nan_mask)[0]
        clean_vals = arr[clean_idx]
        if len(clean_vals) == 0:
            return TransformResult(values=[float("nan")] * len(values), params={})

        from scipy.stats import rankdata
        ranks = rankdata(clean_vals, method=self.method)

        if self.normalize:
            ranks = ranks / len(ranks)

        result_arr = np.full(len(values), float("nan"))
        result_arr[clean_idx] = ranks
        return TransformResult(values=result_arr.tolist(), params={"method": self.method, "normalized": self.normalize})


# ---- Clip Transformer ----

class ClipTransformer(BaseTransformer):
    """Clip values to [lower, upper] bounds.

    Args:
        lower: Lower bound (None = no lower bound).
        upper: Upper bound (None = no upper bound).
    """

    name = "clip"

    def __init__(self, lower: Optional[float] = None, upper: Optional[float] = None) -> None:
        self.lower = lower
        self.upper = upper

    def fit(self, values: List[float]) -> TransformContext:
        return TransformContext(params={"lower": self.lower, "upper": self.upper})

    def transform(self, values: List[float], ctx: Optional[TransformContext] = None) -> TransformResult:
        lower = self.lower
        upper = self.upper
        if ctx:
            lower = ctx.params.get("lower", lower)
            upper = ctx.params.get("upper", upper)

        result: List[float] = []
        for v in values:
            if v is None or (isinstance(v, float) and np.isnan(v)):
                result.append(float("nan"))
            else:
                val = float(v)
                if lower is not None:
                    val = max(lower, val)
                if upper is not None:
                    val = min(upper, val)
                result.append(val)
        return TransformResult(values=result, params={"lower": lower, "upper": upper})


# ---- Winsorize Transformer ----

class WinsorizeTransformer(BaseTransformer):
    """Winsorization: clip values at given percentiles.

    Args:
        limits: Tuple of (lower_percentile, upper_percentile) as fractions.
               e.g. (0.01, 0.01) clips at 1st and 99th percentile.
    """

    name = "winsorize"

    def __init__(self, limits: Tuple[float, float] = (0.01, 0.01)) -> None:
        self.limits = limits

    def fit(self, values: List[float]) -> TransformContext:
        arr = np.array([v for v in values if v is not None and not np.isnan(v)], dtype=np.float64)
        if len(arr) == 0:
            return TransformContext(params={"lower": None, "upper": None})
        lo = float(np.percentile(arr, self.limits[0] * 100))
        hi = float(np.percentile(arr, (1 - self.limits[1]) * 100))
        return TransformContext(params={"lower": lo, "upper": hi})

    def transform(self, values: List[float], ctx: Optional[TransformContext] = None) -> TransformResult:
        if ctx is None or ctx.params.get("lower") is None:
            ctx = self.fit(values)
        lo = ctx.params.get("lower")
        hi = ctx.params.get("upper")

        result: List[float] = []
        for v in values:
            if v is None or (isinstance(v, float) and np.isnan(v)):
                result.append(float("nan"))
            else:
                val = float(v)
                if lo is not None:
                    val = max(lo, val)
                if hi is not None:
                    val = min(hi, val)
                result.append(val)
        return TransformResult(values=result, params=ctx.params)

    def inverse_transform(self, values: List[float], ctx: TransformContext) -> List[float]:
        return list(values)  # winsorization is not invertible
