"""
Experiment variant definitions.

Defines the data structures for experiment
variants including control and treatment groups
with traffic allocation weights.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Variant:
    """
    An experiment variant (control or treatment).

    Attributes:
        variant_id: Unique variant identifier.
        name: Human-readable name.
        is_control: Whether this is the control group.
        weight: Traffic allocation weight (relative).
        value: Value to return when this variant is selected.
        description: Human-readable description.
        metadata: Additional key-value metadata.
    """

    variant_id: str = ""
    name: str = ""
    is_control: bool = False
    weight: float = 1.0
    value: Any = None
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "variant_id": self.variant_id,
            "name": self.name,
            "is_control": self.is_control,
            "weight": self.weight,
            "value": self.value,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Variant":
        """Create from dictionary."""
        return cls(
            variant_id=data.get("variant_id", ""),
            name=data.get("name", ""),
            is_control=data.get("is_control", False),
            weight=data.get("weight", 1.0),
            value=data.get("value"),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
        )


def create_ab_variants(
    control_value: Any = False,
    treatment_value: Any = True,
    control_weight: float = 50.0,
    treatment_weight: float = 50.0,
) -> List[Variant]:
    """
    Create a standard A/B test variant pair.

    Args:
        control_value: Value for control group.
        treatment_value: Value for treatment group.
        control_weight: Traffic weight for control.
        treatment_weight: Traffic weight for treatment.

    Returns:
        List of two Variant objects.
    """
    return [
        Variant(
            variant_id="control",
            name="Control",
            is_control=True,
            weight=control_weight,
            value=control_value,
        ),
        Variant(
            variant_id="treatment",
            name="Treatment",
            is_control=False,
            weight=treatment_weight,
            value=treatment_value,
        ),
    ]


def create_abc_variants(
    control_value: Any = False,
    treatment_a_value: Any = "A",
    treatment_b_value: Any = "B",
    weights: Optional[List[float]] = None,
) -> List[Variant]:
    """
    Create an A/B/C test variant set.

    Args:
        control_value: Value for control group.
        treatment_a_value: Value for treatment A.
        treatment_b_value: Value for treatment B.
        weights: Traffic weights [control, A, B].

    Returns:
        List of three Variant objects.
    """
    w = weights or [34.0, 33.0, 33.0]
    return [
        Variant(
            variant_id="control",
            name="Control",
            is_control=True,
            weight=w[0],
            value=control_value,
        ),
        Variant(
            variant_id="treatment-a",
            name="Treatment A",
            is_control=False,
            weight=w[1],
            value=treatment_a_value,
        ),
        Variant(
            variant_id="treatment-b",
            name="Treatment B",
            is_control=False,
            weight=w[2],
            value=treatment_b_value,
        ),
    ]
