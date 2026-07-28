"""Date delta calculator and temporal bias utilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class TemporalBiasConfig:
    """Configuration for temporal bias computation.

    Attributes:
        scale: Multiplier applied to the raw delta.
        normalize: If True, delta is normalized to days; otherwise seconds.
    """

    scale: float = 1.0
    normalize: bool = True


class DateDeltaCalculator:
    """Calculates date/time deltas and temporal biases.

    Used within the knowledge-graph pipeline to quantify how far
    actual completion dates deviate from expected due dates, enabling
    downstream causal and confidence scoring.
    """

    def compute_temporal_bias(
        self,
        completion_date: date,
        due_date: date,
        config: TemporalBiasConfig | None = None,
    ) -> float:
        """Compute the temporal bias between a completion date and due date.

        A positive return value indicates the completion was *late*
        (completion > due), while a negative value indicates it was
        *early* (completion < due).

        Args:
            completion_date: The date on which the event completed.
            due_date:        The date on which the event was expected.
            config:          Optional configuration controlling scaling and
                             normalisation; defaults to ``TemporalBiasConfig()``.

        Returns:
            float: The temporal bias score.
        """
        if config is None:
            config = TemporalBiasConfig()

        # Normalise both inputs to datetime so we can compute a timedelta.
        _completion = _to_datetime(completion_date)
        _due = _to_datetime(due_date)
        delta_seconds = (_completion - _due).total_seconds()

        if config.normalize:
            return (delta_seconds / 86_400) * config.scale  # days
        return delta_seconds * config.scale


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _to_datetime(d: date) -> datetime:
    """Coerce a ``date`` to ``datetime`` if necessary."""
    if isinstance(d, datetime):
        return d
    return datetime(d.year, d.month, d.day)
