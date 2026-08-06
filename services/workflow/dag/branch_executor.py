"""
Branch Executor — executes conditional branches (IF/ELSE/SWITCH/MATCH).

Dynamically determines the next node(s) based on runtime conditions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from services.workflow.dag.condition import (
    Condition, ConditionGroup, ConditionEvaluator, LogicalOperator,
)

logger = logging.getLogger(__name__)


class BranchType(str, Enum):
    IF = "if"
    IF_ELSE = "if_else"
    SWITCH = "switch"
    MATCH = "match"


@dataclass
class BranchDefinition:
    """Definition of a conditional branch."""

    branch_type: BranchType
    conditions: Dict[str, ConditionGroup] = field(default_factory=dict)
    branches: Dict[str, List[str]] = field(default_factory=dict)
    default_branch: Optional[List[str]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BranchResult:
    """Result of branch evaluation."""

    selected_branch: str
    next_nodes: List[str]
    condition_result: Optional[bool] = None


class BranchExecutor:
    """
    Evaluates conditional branches and determines execution flow.

    Supports:
    - IF: single condition → true branch
    - IF/ELSE: condition → true/false branches
    - SWITCH: value matching → case branch
    - MATCH: pattern matching → first matching branch
    """

    def __init__(self, evaluator: Optional[ConditionEvaluator] = None):
        self.evaluator = evaluator or ConditionEvaluator()

    async def execute(
        self,
        branch_def: BranchDefinition,
        context: Dict[str, Any],
    ) -> BranchResult:
        """
        Evaluate the branch and determine the next nodes.

        Args:
            branch_def: The branch definition.
            context: Runtime context for condition evaluation.

        Returns:
            BranchResult with selected branch and next node IDs.
        """
        if branch_def.branch_type == BranchType.IF:
            return await self._execute_if(branch_def, context)
        elif branch_def.branch_type == BranchType.IF_ELSE:
            return await self._execute_if_else(branch_def, context)
        elif branch_def.branch_type == BranchType.SWITCH:
            return await self._execute_switch(branch_def, context)
        elif branch_def.branch_type == BranchType.MATCH:
            return await self._execute_match(branch_def, context)
        else:
            raise ValueError(f"Unknown branch type: {branch_def.branch_type}")

    async def _execute_if(
        self, branch_def: BranchDefinition, context: Dict[str, Any]
    ) -> BranchResult:
        """Execute IF branch."""
        for branch_name, condition in branch_def.conditions.items():
            if condition.evaluate(context):
                return BranchResult(
                    selected_branch=branch_name,
                    next_nodes=branch_def.branches.get(branch_name, []),
                    condition_result=True,
                )

        # No condition matched
        if branch_def.default_branch:
            return BranchResult(
                selected_branch="default",
                next_nodes=branch_def.default_branch,
                condition_result=False,
            )
        return BranchResult(
            selected_branch="default",
            next_nodes=[],
            condition_result=False,
        )

    async def _execute_if_else(
        self, branch_def: BranchDefinition, context: Dict[str, Any]
    ) -> BranchResult:
        """Execute IF/ELSE branch."""
        if_condition = branch_def.conditions.get("if")
        if if_condition and if_condition.evaluate(context):
            return BranchResult(
                selected_branch="if",
                next_nodes=branch_def.branches.get("if", []),
                condition_result=True,
            )
        return BranchResult(
            selected_branch="else",
            next_nodes=branch_def.branches.get("else", branch_def.default_branch or []),
            condition_result=False,
        )

    async def _execute_switch(
        self, branch_def: BranchDefinition, context: Dict[str, Any]
    ) -> BranchResult:
        """Execute SWITCH branch."""
        switch_value = context.get("_switch_value")
        for branch_name, next_nodes in branch_def.branches.items():
            if branch_name == str(switch_value):
                return BranchResult(
                    selected_branch=branch_name,
                    next_nodes=next_nodes,
                )
        return BranchResult(
            selected_branch="default",
            next_nodes=branch_def.default_branch or [],
        )

    async def _execute_match(
        self, branch_def: BranchDefinition, context: Dict[str, Any]
    ) -> BranchResult:
        """Execute MATCH branch (first condition that matches)."""
        for branch_name, condition in branch_def.conditions.items():
            if condition.evaluate(context):
                return BranchResult(
                    selected_branch=branch_name,
                    next_nodes=branch_def.branches.get(branch_name, []),
                    condition_result=True,
                )
        return BranchResult(
            selected_branch="default",
            next_nodes=branch_def.default_branch or [],
            condition_result=False,
        )
