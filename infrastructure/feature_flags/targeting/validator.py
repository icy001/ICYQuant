"""
Targeting rule validator.

Validates rule definitions, expressions,
and configurations before they are compiled
and used for evaluation. Ensures data integrity
and prevents invalid rule configurations.

Validates:
    - Expression syntax
    - Rule attribute completeness
    - Operator-value compatibility
    - Nested group depth limits
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

from .conditions import RuleNode, node_count, node_depth
from .context import TargetContext
from .operators import Operator
from .parser import ParseError, RuleParser
from .rules import TargetRule

logger = logging.getLogger(__name__)

MAX_NESTING_DEPTH = 10
MAX_CONDITIONS = 50
MAX_RULES_PER_FLAG = 100


class RuleValidator:
    """
    Validates targeting rules and expressions.

    Ensures rules are well-formed before they
    enter the compilation and evaluation pipeline.

    Usage:
        validator = RuleValidator()
        errors = validator.validate_rule(rule)
        if errors:
            print("Validation failed:", errors)
    """

    def __init__(
        self,
        max_nesting_depth: int = MAX_NESTING_DEPTH,
        max_conditions: int = MAX_CONDITIONS,
        max_rules_per_flag: int = MAX_RULES_PER_FLAG,
    ) -> None:
        self._parser = RuleParser()
        self._max_nesting_depth = max_nesting_depth
        self._max_conditions = max_conditions
        self._max_rules_per_flag = max_rules_per_flag
        self._validation_count = 0
        self._error_count = 0

    def validate_rule(self, rule: TargetRule) -> List[str]:
        """
        Validate a single rule definition.

        Args:
            rule: Target rule to validate.

        Returns:
            List of validation error messages.
        """
        self._validation_count += 1
        errors: List[str] = []

        # Check required fields
        if not rule.rule_id:
            errors.append("Rule ID is required")

        # Check expression
        if not rule.expression:
            errors.append("Expression is required")
        elif rule.expression.strip():
            expr_errors = self._validate_expression(rule.expression)
            errors.extend(expr_errors)

        # Check value
        if rule.value is None:
            errors.append("Rule value is required")

        # Check priority
        if rule.priority < 0:
            errors.append("Priority must be non-negative")

        if errors:
            self._error_count += len(errors)

        return errors

    def validate_rules(self, rules: List[TargetRule]) -> List[str]:
        """
        Validate a list of rules.

        Args:
            rules: List of rules to validate.

        Returns:
            List of validation error messages.
        """
        errors: List[str] = []

        if len(rules) > self._max_rules_per_flag:
            errors.append(
                f"Too many rules ({len(rules)}/{self._max_rules_per_flag})"
            )

        rule_ids = set()
        for i, rule in enumerate(rules):
            rule_errors = self.validate_rule(rule)
            for err in rule_errors:
                errors.append(f"Rule[{i}]: {err}")

            if rule.rule_id in rule_ids:
                errors.append(f"Duplicate rule ID: {rule.rule_id}")
            rule_ids.add(rule.rule_id)

        return errors

    def _validate_expression(self, expression: str) -> List[str]:
        """Validate an expression string."""
        errors: List[str] = []

        try:
            node = self._parser.parse(expression)

            # Check nesting depth
            depth = node_depth(node)
            if depth > self._max_nesting_depth:
                errors.append(
                    f"Expression exceeds max nesting depth "
                    f"({depth}/{self._max_nesting_depth})"
                )

            # Check condition count
            count = node_count(node)
            if count > self._max_conditions:
                errors.append(
                    f"Expression exceeds max conditions "
                    f"({count}/{self._max_conditions})"
                )

        except ParseError as e:
            errors.append(f"Parse error: {str(e)}")
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")

        return errors

    def validate_expression_syntax(self, expression: str) -> List[str]:
        """
        Validate expression syntax only (structural check).

        Args:
            expression: Expression string.

        Returns:
            List of syntax errors.
        """
        errors: List[str] = []

        if not expression or not expression.strip():
            return errors

        # Check balanced parentheses
        depth = 0
        for ch in expression:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth < 0:
                errors.append("Unmatched closing parenthesis")
                break

        if depth > 0:
            errors.append(f"Unmatched opening parenthesis ({depth})")

        # Check for common syntax issues
        expr_upper = expression.upper()
        for keyword in ["AND", "OR"]:
            # Check for double operators (e.g., "AND AND")
            pattern = f"\\b{keyword}\\s+{keyword}\\b"
            if re.search(pattern, expr_upper):
                errors.append(f"Double '{keyword}' operator detected")

        return errors

    def get_stats(self) -> dict:
        """Get validator statistics."""
        return {
            "validations": self._validation_count,
            "errors": self._error_count,
            "error_rate": (
                self._error_count / self._validation_count
                if self._validation_count > 0 else 0.0
            ),
        }