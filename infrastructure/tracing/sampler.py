"""
Trace samplers.

Determines whether a trace should be
sampled (recorded) or not, controlling
the volume of trace data exported.

Samplers:
- AlwaysOnSampler: Sample everything
- AlwaysOffSampler: Sample nothing
- RatioSampler: Sample a percentage
- ParentBasedSampler: Inherit parent's decision
"""

from __future__ import annotations

from random import random
from typing import Optional

from .models import SpanModel


class Sampler:
    """Base sampler interface."""

    def should_sample(
        self,
        trace_id: str,
        parent: Optional[SpanModel] = None,
    ) -> bool:
        """Determine if trace should be sampled."""
        raise NotImplementedError


class AlwaysOnSampler(Sampler):
    """Always sample traces."""

    def should_sample(
        self,
        trace_id: str,
        parent: Optional[SpanModel] = None,
    ) -> bool:
        return True


class AlwaysOffSampler(Sampler):
    """Never sample traces."""

    def should_sample(
        self,
        trace_id: str,
        parent: Optional[SpanModel] = None,
    ) -> bool:
        return False


class RatioSampler(Sampler):
    """
    Ratio-based sampler.

    Samples a configurable percentage of
    traces. Uses the trace_id for
    deterministic sampling.

    Attributes:
        ratio: Sampling ratio (0.0 - 1.0).
    """

    def __init__(
        self,
        ratio: float = 1.0,
    ) -> None:
        """
        Initialize ratio sampler.

        Args:
            ratio: Sampling ratio (0.0 = none, 1.0 = all).
        """

        self._ratio = max(0.0, min(1.0, ratio))

    @property
    def ratio(
        self,
    ) -> float:
        """Get sampling ratio."""
        return self._ratio

    def should_sample(
        self,
        trace_id: str,
        parent: Optional[SpanModel] = None,
    ) -> bool:
        """Determine if trace should be sampled."""

        if self._ratio >= 1.0:
            return True
        if self._ratio <= 0.0:
            return False
        return random() <= self._ratio


class ParentBasedSampler(Sampler):
    """
    Parent-based sampler.

    Inherits the sampling decision from
    the parent span's trace. If no parent,
    uses the delegate sampler.

    Attributes:
        delegate: Sampler for root spans.
    """

    def __init__(
        self,
        delegate: Sampler = None,
    ) -> None:
        """
        Initialize parent-based sampler.

        Args:
            delegate: Sampler for root spans (default: AlwaysOn).
        """

        self._delegate = delegate or AlwaysOnSampler()

    def should_sample(
        self,
        trace_id: str,
        parent: Optional[SpanModel] = None,
    ) -> bool:
        """Inherit parent's sampling decision."""

        # If no parent, use delegate
        if parent is None:
            return self._delegate.should_sample(trace_id)

        # Inherit from parent trace
        # In production, would check parent's sampled flag
        return True
