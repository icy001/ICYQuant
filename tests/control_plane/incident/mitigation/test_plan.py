"""Tests for the mitigation plan model (spec section 9)."""
from __future__ import annotations

from services.control_plane.incident.mitigation.action import MitigationAction
from services.control_plane.incident.mitigation.action_type import (
    MitigationActionType,
)
from services.control_plane.incident.mitigation.plan import MitigationPlan


def test_plan_defaults():
    plan = MitigationPlan(incident_id="INC-1")

    assert plan.incident_id == "INC-1"
    assert plan.actions == []
    assert plan.parallel is False
    assert plan.fail_fast is True


def test_plan_add_appends_actions():
    plan = MitigationPlan(incident_id="INC-1")
    first = MitigationAction(
        incident_id="INC-1",
        action_type=MitigationActionType.CANCEL_OPEN_ORDERS,
    )
    second = MitigationAction(
        incident_id="INC-1",
        action_type=MitigationActionType.BLOCK_NEW_ORDERS,
    )

    plan.add(first)
    plan.add(second)

    assert plan.actions == [first, second]


def test_plan_carries_best_effort_and_parallel_flags():
    plan = MitigationPlan(
        incident_id="INC-1",
        parallel=True,
        fail_fast=False,
    )

    assert plan.parallel is True
    assert plan.fail_fast is False
