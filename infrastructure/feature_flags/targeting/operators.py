"""
Targeting rule operators.

Defines comparison operators for rule-based
targeting evaluation. Each operator implements
a compare function that tests an attribute
value against an expected value.

Supported operators:
    ==, !=, >, >=, <, <=,
    IN, NOT_IN, STARTS_WITH, ENDS_WITH,
    CONTAINS, REGEX
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class Operator(str, Enum):
    """
    Supported comparison operators for targeting rules.

    Each operator has a symbol, a precedence for parsing,
    and a compare function.
    """

    EQ = "=="
    NEQ = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    IN = "IN"
    NOT_IN = "NOT_IN"
    STARTS_WITH = "STARTS_WITH"
    ENDS_WITH = "ENDS_WITH"
    CONTAINS = "CONTAINS"
    REGEX = "REGEX"


OperatorDef = Tuple[str, Callable[[Any, Any], bool], int]

# Operator name mapping for parsing
OPERATOR_SYMBOLS: Dict[str, Operator] = {
    "==": Operator.EQ,
    "!=": Operator.NEQ,
    ">=": Operator.GTE,
    "<=": Operator.LTE,
    ">": Operator.GT,
    "<": Operator.LT,
    " IN ": Operator.IN,
    " NOT IN ": Operator.NOT_IN,
    " STARTS_WITH ": Operator.STARTS_WITH,
    " ENDS_WITH ": Operator.ENDS_WITH,
    " CONTAINS ": Operator.CONTAINS,
    " REGEX ": Operator.REGEX,
}

# Ordered list for parsing (longest match first)
OPERATOR_ORDER: List[Tuple[str, Operator]] = [
    ("STARTS_WITH", Operator.STARTS_WITH),
    ("ENDS_WITH", Operator.ENDS_WITH),
    ("CONTAINS", Operator.CONTAINS),
    ("REGEX", Operator.REGEX),
    ("NOT_IN", Operator.NOT_IN),
    ("IN", Operator.IN),
    (">=", Operator.GTE),
    ("<=", Operator.LTE),
    ("==", Operator.EQ),
    ("!=", Operator.NEQ),
    (">", Operator.GT),
    ("<", Operator.LT),
]


def _try_numeric(value: Any) -> Optional[float]:
    """Try to convert a value to a number."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().strip("'\""))
        except (ValueError, TypeError):
            return None
    return None


def compare_eq(actual: Any, expected: Any) -> bool:
    """Equality comparison."""
    if actual is None:
        return str(expected).lower() == "none"
    return str(actual).lower() == str(expected).lower()


def compare_neq(actual: Any, expected: Any) -> bool:
    """Not-equal comparison."""
    return not compare_eq(actual, expected)


def compare_gt(actual: Any, expected: Any) -> bool:
    """Greater-than comparison."""
    a = _try_numeric(actual)
    b = _try_numeric(expected)
    if a is not None and b is not None:
        return a > b
    return str(actual) > str(expected)


def compare_gte(actual: Any, expected: Any) -> bool:
    """Greater-than-or-equal comparison."""
    a = _try_numeric(actual)
    b = _try_numeric(expected)
    if a is not None and b is not None:
        return a >= b
    return str(actual) >= str(expected)


def compare_lt(actual: Any, expected: Any) -> bool:
    """Less-than comparison."""
    a = _try_numeric(actual)
    b = _try_numeric(expected)
    if a is not None and b is not None:
        return a < b
    return str(actual) < str(expected)


def compare_lte(actual: Any, expected: Any) -> bool:
    """Less-than-or-equal comparison."""
    a = _try_numeric(actual)
    b = _try_numeric(expected)
    if a is not None and b is not None:
        return a <= b
    return str(actual) <= str(expected)


def compare_in(actual: Any, expected: Any) -> bool:
    """Membership check (value in set)."""
    if isinstance(expected, (list, tuple, set)):
        values = [str(v).lower() for v in expected]
        return str(actual).lower() in values
    if isinstance(expected, str):
        values = [v.strip().strip("'\"") for v in expected.split(",")]
        return str(actual).lower() in [v.lower() for v in values]
    return False


def compare_not_in(actual: Any, expected: Any) -> bool:
    """Non-membership check."""
    return not compare_in(actual, expected)


def compare_starts_with(actual: Any, expected: Any) -> bool:
    """String starts-with check."""
    if actual is None:
        return False
    return str(actual).lower().startswith(str(expected).lower())


def compare_ends_with(actual: Any, expected: Any) -> bool:
    """String ends-with check."""
    if actual is None:
        return False
    return str(actual).lower().endswith(str(expected).lower())


def compare_contains(actual: Any, expected: Any) -> bool:
    """String contains check."""
    if actual is None:
        return False
    return str(expected).lower() in str(actual).lower()


def compare_regex(actual: Any, expected: Any) -> bool:
    """Regex match check."""
    if actual is None:
        return False
    try:
        return bool(re.search(str(expected), str(actual), re.IGNORECASE))
    except re.error:
        return False


COMPARE_FUNCTIONS: Dict[Operator, Callable[[Any, Any], bool]] = {
    Operator.EQ: compare_eq,
    Operator.NEQ: compare_neq,
    Operator.GT: compare_gt,
    Operator.GTE: compare_gte,
    Operator.LT: compare_lt,
    Operator.LTE: compare_lte,
    Operator.IN: compare_in,
    Operator.NOT_IN: compare_not_in,
    Operator.STARTS_WITH: compare_starts_with,
    Operator.ENDS_WITH: compare_ends_with,
    Operator.CONTAINS: compare_contains,
    Operator.REGEX: compare_regex,
}


def get_compare_fn(operator: Operator) -> Callable[[Any, Any], bool]:
    """Get the compare function for an operator."""
    return COMPARE_FUNCTIONS.get(operator, compare_eq)


def find_operator(expression: str) -> Optional[Tuple[str, Operator]]:
    """
    Find the first operator in an expression string.

    Args:
        expression: The expression to search.

    Returns:
        Tuple of (operator_symbol, Operator) or None.
    """
    expr_upper = expression.upper()
    for symbol, op in OPERATOR_ORDER:
        idx = expr_upper.find(symbol)
        if idx >= 0:
            # Make sure it's not part of a longer keyword
            if symbol in ("IN", "NOT_IN"):
                # Check it's not CONTAINS / NOT_IN / etc
                if symbol == "IN":
                    context = expr_upper[max(0, idx - 1):idx + len(symbol) + 1]
                    if "NOT_IN" in context or "CONTAINS" in context:
                        continue
            return symbol, op
    return None