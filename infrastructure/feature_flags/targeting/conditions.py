"""
Targeting rule conditions.

Provides condition node types for building
expression trees (AST) for rule evaluation.
Supports AND, OR, NOT, and nested groups.

Example:
    (account == "001") AND (exchange == "NASDAQ")
    ↓
    AndNode(
        left=ConditionNode("account", "==", "001"),
        right=ConditionNode("exchange", "==", "NASDAQ"),
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Union

from .operators import Operator


@dataclass
class ConditionNode:
    """
    A leaf condition node (attribute comparison).

    Represents a single comparison like:
        account == "001"
        exchange IN (NYSE, NASDAQ)

    Attributes:
        attribute: Context attribute name.
        operator: Comparison operator.
        value: Expected value.
        raw_expression: Original expression string.
    """

    attribute: str = ""
    operator: Operator = Operator.EQ
    value: Any = None
    raw_expression: str = ""

    def to_dict(self) -> dict:
        return {
            "type": "condition",
            "attribute": self.attribute,
            "operator": self.operator.value,
            "value": self.value,
            "raw": self.raw_expression,
        }


@dataclass
class AndNode:
    """
    AND logical combination.

    All child conditions must be true for
    the AND node to be true.

    Attributes:
    children: List of child nodes (any node type).
    """

    children: List[Union[ConditionNode, AndNode, OrNode, NotNode]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": "and",
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class OrNode:
    """
    OR logical combination.

    At least one child condition must be true
    for the OR node to be true.

    Attributes:
    children: List of child nodes (any node type).
    """

    children: List[Union[ConditionNode, AndNode, OrNode, NotNode]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "type": "or",
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class NotNode:
    """
    NOT logical negation.

    Negates the result of a single child node.

    Attributes:
    child: The node to negate.
    """

    child: Union[ConditionNode, AndNode, OrNode, NotNode] = None

    def to_dict(self) -> dict:
        return {
            "type": "not",
            "child": self.child.to_dict() if self.child else None,
        }


LogicNode = Union[AndNode, OrNode, NotNode]
RuleNode = Union[ConditionNode, AndNode, OrNode, NotNode]


def node_count(node: RuleNode) -> int:
    """Count the number of leaf conditions in a node tree."""
    if isinstance(node, ConditionNode):
        return 1
    elif isinstance(node, NotNode):
        return node_count(node.child) if node.child else 0
    elif isinstance(node, (AndNode, OrNode)):
        return sum(node_count(c) for c in node.children)
    return 0


def node_depth(node: RuleNode) -> int:
    """Calculate the maximum depth of a node tree."""
    if isinstance(node, ConditionNode):
        return 1
    elif isinstance(node, NotNode):
        return 1 + (node_depth(node.child) if node.child else 0)
    elif isinstance(node, (AndNode, OrNode)):
        if not node.children:
            return 1
        return 1 + max(node_depth(c) for c in node.children)
    return 1


def flatten_conditions(node: RuleNode) -> List[ConditionNode]:
    """Extract all leaf conditions from a node tree."""
    result: List[ConditionNode] = []
    if isinstance(node, ConditionNode):
        result.append(node)
    elif isinstance(node, NotNode):
        result.extend(flatten_conditions(node.child))
    elif isinstance(node, (AndNode, OrNode)):
        for child in node.children:
            result.extend(flatten_conditions(child))
    return result