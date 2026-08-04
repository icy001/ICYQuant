"""
Targeting rule expression parser.

Parses rule expression strings into an AST
(Abstract Syntax Tree) represented as a tree
of ConditionNode, AndNode, OrNode, NotNode.

Supports:
    - Simple comparisons: attribute == value
    - AND/OR/NOT logical operators
    - Nested groups with parentheses
    - Complex expressions:
        (account == "001") AND (exchange == "NASDAQ")
        environment == "production" AND broker IN ("IBKR", "OANDA")

Grammar:
    expression  → or_expr
    or_expr     → and_expr ("OR" and_expr)*
    and_expr    → not_expr ("AND" not_expr)*
    not_expr    → "NOT" not_expr | primary
    primary     → "(" expression ")" | condition
    condition   → attribute operator value
"""

from __future__ import annotations

import logging
import re
from typing import Any, List, Optional, Tuple

from .conditions import (
    AndNode,
    ConditionNode,
    OrNode,
    RuleNode,
)
from .operators import Operator

logger = logging.getLogger(__name__)


class ParseError(Exception):
    """Raised when expression parsing fails."""

    def __init__(self, message: str, position: int = -1) -> None:
        self.position = position
        super().__init__(f"Parse error at position {position}: {message}")


class RuleParser:
    """
    Parses rule expression strings into AST.

    Implements a recursive descent parser for
    the targeting rule expression grammar.

    Usage:
        parser = RuleParser()
        ast = parser.parse("account == '001' AND exchange == 'NASDAQ'")
    """

    def __init__(self) -> None:
        self._cache: dict = {}

    def parse(self, expression: str) -> RuleNode:
        """
        Parse an expression string into an AST.

        Args:
            expression: Rule expression string.

        Returns:
            Root node of the AST.

        Raises:
            ParseError: If the expression is invalid.
        """
        if not expression or not expression.strip():
            return ConditionNode(
                attribute="true",
                raw_expression="true",
            )

        expr = expression.strip()

        if expr in self._cache:
            return self._cache[expr]

        pos = [0]
        result = self._parse_or(expr, pos)

        # Skip trailing whitespace
        self._skip_whitespace(expr, pos)

        if pos[0] < len(expr):
            raise ParseError(
                f"Unexpected character at position {pos[0]}: '{expr[pos[0]:pos[0]+10]}'",
                pos[0],
            )

        self._cache[expr] = result
        return result

    def clear_cache(self) -> None:
        """Clear the parse cache."""
        self._cache.clear()

    def _skip_whitespace(self, expr: str, pos: List[int]) -> None:
        """Skip whitespace characters."""
        while pos[0] < len(expr) and expr[pos[0]] in (" ", "\t", "\n"):
            pos[0] += 1

    def _parse_or(self, expr: str, pos: List[int]) -> RuleNode:
        """Parse OR expressions (lowest precedence)."""
        left = self._parse_and(expr, pos)

        self._skip_whitespace(expr, pos)
        while pos[0] < len(expr):
            if self._match_keyword(expr, pos, "OR"):
                self._skip_whitespace(expr, pos)
                right = self._parse_and(expr, pos)
                left = OrNode(children=[left, right])
                self._skip_whitespace(expr, pos)
            else:
                break

        return left

    def _parse_and(self, expr: str, pos: List[int]) -> RuleNode:
        """Parse AND expressions."""
        left = self._parse_not(expr, pos)

        self._skip_whitespace(expr, pos)
        while pos[0] < len(expr):
            if self._match_keyword(expr, pos, "AND"):
                self._skip_whitespace(expr, pos)
                right = self._parse_not(expr, pos)
                left = AndNode(children=[left, right])
                self._skip_whitespace(expr, pos)
            else:
                break

        return left

    def _parse_not(self, expr: str, pos: List[int]) -> RuleNode:
        """Parse NOT expressions (highest precedence among logical ops)."""
        self._skip_whitespace(expr, pos)
        if self._match_keyword(expr, pos, "NOT"):
            self._skip_whitespace(expr, pos)
            child = self._parse_not(expr, pos)
            from .conditions import NotNode
            return NotNode(child=child)
        return self._parse_primary(expr, pos)

    def _parse_primary(self, expr: str, pos: List[int]) -> RuleNode:
        """Parse primary expressions (groups or conditions)."""
        self._skip_whitespace(expr, pos)

        if pos[0] >= len(expr):
            raise ParseError("Unexpected end of expression", pos[0])

        # Group
        if expr[pos[0]] == "(":
            pos[0] += 1  # Skip opening paren
            self._skip_whitespace(expr, pos)
            inner = self._parse_or(expr, pos)
            self._skip_whitespace(expr, pos)

            if pos[0] >= len(expr) or expr[pos[0]] != ")":
                raise ParseError(
                    "Expected closing parenthesis",
                    pos[0],
                )
            pos[0] += 1  # Skip closing paren
            return inner

        # Condition
        return self._parse_condition(expr, pos)

    def _parse_condition(self, expr: str, pos: List[int]) -> ConditionNode:
        """Parse a single condition: attribute operator value."""
        start_pos = pos[0]

        # Read attribute name
        attr = self._read_attribute(expr, pos)
        if not attr:
            raise ParseError(
                f"Expected attribute name at position {pos[0]}",
                pos[0],
            )

        self._skip_whitespace(expr, pos)

        # Read operator
        op_result = self._read_operator(expr, pos)
        if op_result is None:
            raise ParseError(
                f"Expected operator after attribute '{attr}'",
                pos[0],
            )

        op_symbol, operator = op_result
        self._skip_whitespace(expr, pos)

        # Handle IN with parentheses: IN (val1, val2)
        if operator == Operator.IN or operator == Operator.NOT_IN:
            value = self._read_in_value(expr, pos)
        else:
            # Read value
            value = self._read_value(expr, pos)

        raw = expr[start_pos:pos[0]].strip()

        return ConditionNode(
            attribute=attr,
            operator=operator,
            value=value,
            raw_expression=raw,
        )

    def _read_attribute(self, expr: str, pos: List[int]) -> str:
        """Read an attribute name (alphanumeric + underscore + dot)."""
        start = pos[0]
        while pos[0] < len(expr):
            ch = expr[pos[0]]
            if ch.isalnum() or ch in ("_", ".", "-"):
                pos[0] += 1
            else:
                break
        return expr[start:pos[0]]

    def _read_operator(
        self, expr: str, pos: List[int],
    ) -> Optional[Tuple[str, Operator]]:
        """Read an operator from the expression."""
        remaining = expr[pos[0]:]

        # Try multi-char operators first
        for symbol, op in [
            ("STARTS_WITH", Operator.STARTS_WITH),
            ("ENDS_WITH", Operator.ENDS_WITH),
            ("CONTAINS", Operator.CONTAINS),
            ("REGEX", Operator.REGEX),
            ("NOT_IN", Operator.NOT_IN),
            ("NOT IN", Operator.NOT_IN),
            (">=", Operator.GTE),
            ("<=", Operator.LTE),
            ("==", Operator.EQ),
            ("!=", Operator.NEQ),
            ("IN", Operator.IN),
            (">", Operator.GT),
            ("<", Operator.LT),
        ]:
            if remaining.upper().startswith(symbol):
                # For IN, ensure it's not part of a longer keyword
                if symbol == "IN":
                    # Check that it's not "NOT IN"
                    before = expr[max(0, pos[0] - 4):pos[0]].upper()
                    if "NOT" in before:
                        continue
                    # Check next char is not alphanumeric (it's a word boundary)
                    next_pos = pos[0] + len(symbol)
                    if next_pos < len(expr) and (
                        expr[next_pos].isalnum() or expr[next_pos] == "_"
                    ):
                        continue

                pos[0] += len(symbol)
                return symbol, op

        return None

    def _read_in_value(self, expr: str, pos: List[int]) -> Any:
        """Read the value part of an IN operator: (val1, val2, val3)."""
        self._skip_whitespace(expr, pos)

        values: List[str] = []

        # Check for parenthesized list
        if pos[0] < len(expr) and expr[pos[0]] == "(":
            pos[0] += 1
            self._skip_whitespace(expr, pos)

            while pos[0] < len(expr) and expr[pos[0]] != ")":
                self._skip_whitespace(expr, pos)
                val = self._read_value(expr, pos)
                values.append(str(val).strip("'\""))
                self._skip_whitespace(expr, pos)

                if pos[0] < len(expr) and expr[pos[0]] == ",":
                    pos[0] += 1
                elif pos[0] < len(expr) and expr[pos[0]] != ")":
                    raise ParseError(
                        f"Expected ',' or ')' at position {pos[0]}",
                        pos[0],
                    )

            if pos[0] < len(expr) and expr[pos[0]] == ")":
                pos[0] += 1
        else:
            # Inline comma-separated: val1, val2, val3
            start = pos[0]
            while pos[0] < len(expr) and expr[pos[0]] not in ("\n", "\r"):
                # Stop at AND/OR/NOT keywords
                remaining = expr[pos[0]:pos[0] + 20].upper().strip()
                if remaining.startswith("AND ") or remaining.startswith("OR ") or remaining.startswith("NOT "):
                    break
                if expr[pos[0]] == ")":
                    break
                pos[0] += 1
            raw = expr[start:pos[0]].strip()
            values = [v.strip().strip("'\"") for v in raw.split(",")]

        return values

    def _read_value(self, expr: str, pos: List[int]) -> Any:
        """Read a value (string, number, or identifier)."""
        self._skip_whitespace(expr, pos)

        if pos[0] >= len(expr):
            return ""

        ch = expr[pos[0]]

        # Quoted string
        if ch in ("'", '"'):
            quote = ch
            pos[0] += 1
            start = pos[0]
            while pos[0] < len(expr) and expr[pos[0]] != quote:
                if expr[pos[0]] == "\\":
                    pos[0] += 1  # Skip escape
                pos[0] += 1
            value = expr[start:pos[0]]
            if pos[0] < len(expr):
                pos[0] += 1  # Skip closing quote
            return value

        # Number
        if ch.isdigit() or (ch == "-" and pos[0] + 1 < len(expr) and expr[pos[0] + 1].isdigit()):
            start = pos[0]
            if ch == "-":
                pos[0] += 1
            while pos[0] < len(expr) and (expr[pos[0]].isdigit() or expr[pos[0]] == "."):
                pos[0] += 1
            num_str = expr[start:pos[0]]
            try:
                if "." in num_str:
                    return float(num_str)
                return int(num_str)
            except ValueError:
                return num_str

        # Identifier / word
        start = pos[0]
        while pos[0] < len(expr):
            ch = expr[pos[0]]
            if ch.isalnum() or ch in ("_", ".", "-"):
                pos[0] += 1
            else:
                break
        return expr[start:pos[0]]

    def _match_keyword(self, expr: str, pos: List[int], keyword: str) -> bool:
        """Check if a keyword matches at the current position and consume it."""
        remaining = expr[pos[0]:]
        kw_upper = keyword.upper()

        if remaining.upper().startswith(kw_upper):
            # Ensure it's a word boundary
            next_pos = pos[0] + len(kw_upper)
            if next_pos >= len(expr) or not remaining[len(kw_upper):len(kw_upper) + 1].isalnum():
                pos[0] += len(kw_upper)
                return True
        return False


def parse_expression(expression: str) -> RuleNode:
    """
    Parse an expression string into an AST.

    Convenience function that creates a new parser
    and parses the expression.

    Args:
        expression: Rule expression string.

    Returns:
        Root node of the AST.
    """
    parser = RuleParser()
    return parser.parse(expression)