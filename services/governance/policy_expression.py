"""
Policy Expression — composable expression DSL for policy conditions.

Supports:
  - Arithmetic expressions: all of(context.leverage) / context.available_capital
  - Logical combinations: context.var_95 > 0.15 AND context.liquidity < 50
  - Aggregation: SUM, AVG, MIN, MAX, COUNT across multiple metrics
  - Formula evaluation with parameter substitution
  - Custom function registration for domain-specific logic
"""

from __future__ import annotations

import math
import operator as _op
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Expression types
# ---------------------------------------------------------------------------

class ExpressionType(Enum):
    """Types of policy expressions."""

    SIMPLE = auto()       # Simple comparison: metric > threshold
    COMPARISON = auto()   # Comparison with operator: a > b
    LOGICAL = auto()      # Logical combination: a AND b
    ARITHMETIC = auto()   # Arithmetic: a + b * c
    AGGREGATION = auto()  # Aggregation: SUM(values)
    FORMULA = auto()      # Formula with named variables
    CUSTOM = auto()       # Custom function call


class LogicalOperator(Enum):
    """Logical operators for combining sub-expressions."""

    AND = auto()
    OR = auto()
    NOT = auto()
    XOR = auto()


class ArithmeticOperator(Enum):
    """Arithmetic operators for expression evaluation."""

    ADD = auto()
    SUBTRACT = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    POWER = auto()
    MOD = auto()


class AggregationFunction(Enum):
    """Aggregation functions for multi-value expressions."""

    SUM = auto()
    AVG = auto()
    MIN = auto()
    MAX = auto()
    COUNT = auto()
    MEDIAN = auto()
    STDEV = auto()
    PRODUCT = auto()


# ---------------------------------------------------------------------------
# Expression node
# ---------------------------------------------------------------------------

@dataclass
class PolicyExpression:
    """
    A composable policy expression for evaluating conditions.

    Supports tree-structured expressions with various node types:
      - Leaf: direct metric reference or constant
      - Comparison: operator-based comparison
      - Logical: AND/OR/NOT/XOR of sub-expressions
      - Arithmetic: math operations
      - Aggregation: multi-value functions
      - Formula: named-variable expressions
      - Custom: registered function calls

    Example:
        # Portfolio check: (concentration > 0.3 OR leverage > 2.5) AND liquidity < 50
        PolicyExpression(
            expr_type=ExpressionType.LOGICAL,
            logical_op=LogicalOperator.AND,
            left=PolicyExpression(
                expr_type=ExpressionType.LOGICAL,
                logical_op=LogicalOperator.OR,
                left=PolicyExpression(metric="concentration", operator=">", threshold=0.3),
                right=PolicyExpression(metric="leverage", operator=">", threshold=2.5),
            ),
            right=PolicyExpression(metric="liquidity", operator="<", threshold=50),
        )
    """

    # Identity
    expression_id: str = ""
    name: str = ""
    description: str = ""

    # Expression type
    expr_type: ExpressionType = ExpressionType.SIMPLE

    # ---- Leaf: metric reference ----
    metric: str = ""            # Context field name
    operator: str = ""          # Comparison operator: ==, !=, <, <=, >, >=
    threshold: Any = None       # Static threshold
    threshold_metric: str = ""  # Dynamic threshold from another metric

    # ---- Logical ----
    logical_op: Optional[LogicalOperator] = None
    left: Optional[PolicyExpression] = None
    right: Optional[PolicyExpression] = None

    # ---- Arithmetic ----
    arithmetic_op: Optional[ArithmeticOperator] = None
    operands: List[PolicyExpression] = field(default_factory=list)

    # ---- Aggregation ----
    aggregation_func: Optional[AggregationFunction] = None
    aggregation_metrics: List[str] = field(default_factory=list)

    # ---- Formula ----
    formula_template: str = ""                    # e.g., "{var_95} * {portfolio_value}"
    formula_variables: Dict[str, str] = field(default_factory=dict)  # var_name → metric_name

    # ---- Custom ----
    custom_function: str = ""
    custom_args: Dict[str, Any] = field(default_factory=dict)

    # ---- Metadata ----
    severity_on_fail: str = "WARNING"
    enabled: bool = True
    tags: List[str] = field(default_factory=list)

    # ---- Evaluation ----

    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate this expression against a context dictionary.

        Returns: { "result": bool|float|Any, "details": str, "error": str|None }
        """
        if not self.enabled:
            return {"result": True, "details": "expression disabled", "error": None}

        try:
            if self.expr_type == ExpressionType.SIMPLE:
                return self._eval_simple(context)
            elif self.expr_type == ExpressionType.COMPARISON:
                return self._eval_comparison(context)
            elif self.expr_type == ExpressionType.LOGICAL:
                return self._eval_logical(context)
            elif self.expr_type == ExpressionType.ARITHMETIC:
                return self._eval_arithmetic(context)
            elif self.expr_type == ExpressionType.AGGREGATION:
                return self._eval_aggregation(context)
            elif self.expr_type == ExpressionType.FORMULA:
                return self._eval_formula(context)
            elif self.expr_type == ExpressionType.CUSTOM:
                return self._eval_custom(context)
            else:
                return {"result": True, "details": "unknown type", "error": None}
        except Exception as e:
            return {
                "result": False,
                "details": str(e),
                "error": f"Evaluation error: {e}",
            }

    def _eval_simple(self, context: Dict[str, Any]) -> Dict[str, Any]:
        value = self._resolve_metric(self.metric, context)
        if value is None:
            return {
                "result": True,
                "details": f"metric '{self.metric}' not found — pass",
                "error": None,
            }

        threshold = self.threshold
        if self.threshold_metric:
            threshold = self._resolve_metric(self.threshold_metric, context)
            if threshold is None:
                threshold = self.threshold

        passed = self._compare(value, self.operator, threshold)
        return {
            "result": passed,
            "details": f"{self.metric}={value} {self.operator} {threshold} → {'PASS' if passed else 'FAIL'}",
            "error": None,
            "actual": value,
            "expected": f"{self.operator} {threshold}",
        }

    def _eval_comparison(self, context: Dict[str, Any]) -> Dict[str, Any]:
        left_val = self._resolve_expression(self.left, context)
        right_val = self._resolve_expression(self.right, context)

        if left_val is None or right_val is None:
            return {"result": True, "details": "comparison could not resolve — pass", "error": None}

        passed = self._compare(left_val, self.operator, right_val)
        return {
            "result": passed,
            "details": f"{left_val} {self.operator} {right_val} → {'PASS' if passed else 'FAIL'}",
            "error": None,
            "actual": left_val,
            "expected": f"{self.operator} {right_val}",
        }

    def _eval_logical(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.logical_op:
            return {"result": True, "details": "no logical op — pass", "error": None}

        left_result = True
        right_result = True

        if self.left:
            left_result = self.left.evaluate(context).get("result", True)
        if self.right and self.logical_op != LogicalOperator.NOT:
            right_result = self.right.evaluate(context).get("result", True)

        if self.logical_op == LogicalOperator.AND:
            passed = left_result and right_result
        elif self.logical_op == LogicalOperator.OR:
            passed = left_result or right_result
        elif self.logical_op == LogicalOperator.NOT:
            passed = not left_result
        elif self.logical_op == LogicalOperator.XOR:
            passed = left_result != right_result
        else:
            passed = True

        return {
            "result": passed,
            "details": f"{self.logical_op.name}: L={left_result}, R={right_result} → {'PASS' if passed else 'FAIL'}",
            "error": None,
        }

    def _eval_arithmetic(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.arithmetic_op or not self.operands:
            return {"result": 0.0, "details": "no operands", "error": None}

        values = [self._resolve_expression(op, context) or 0.0 for op in self.operands]

        ops_map = {
            ArithmeticOperator.ADD: lambda vs: sum(vs),
            ArithmeticOperator.SUBTRACT: lambda vs: vs[0] - sum(vs[1:]) if len(vs) > 1 else vs[0],
            ArithmeticOperator.MULTIPLY: lambda vs: math.prod(vs),
            ArithmeticOperator.DIVIDE: lambda vs: (
                vs[0] / math.prod(vs[1:]) if len(vs) > 1 and all(v != 0 for v in vs[1:]) else vs[0]
            ),
            ArithmeticOperator.POWER: lambda vs: (
                vs[0] ** vs[1] if len(vs) >= 2 else vs[0]
            ),
            ArithmeticOperator.MOD: lambda vs: (
                vs[0] % vs[1] if len(vs) >= 2 and vs[1] != 0 else vs[0]
            ),
        }

        try:
            result = ops_map[self.arithmetic_op](values)
        except Exception:
            result = 0.0

        return {
            "result": result,
            "details": f"{self.arithmetic_op.name}({values}) = {result}",
            "error": None,
        }

    def _eval_aggregation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.aggregation_func or not self.aggregation_metrics:
            return {"result": 0.0, "details": "no metrics", "error": None}

        values = []
        for metric in self.aggregation_metrics:
            v = self._resolve_metric(metric, context)
            if v is not None and isinstance(v, (int, float)):
                values.append(float(v))

        if not values:
            return {"result": 0.0, "details": "no valid values", "error": None}

        func_map: Dict[AggregationFunction, Callable] = {
            AggregationFunction.SUM: sum,
            AggregationFunction.AVG: lambda vs: sum(vs) / len(vs),
            AggregationFunction.MIN: min,
            AggregationFunction.MAX: max,
            AggregationFunction.COUNT: len,
            AggregationFunction.MEDIAN: lambda vs: sorted(vs)[len(vs) // 2],
            AggregationFunction.STDEV: lambda vs: (
                (sum((x - sum(vs) / len(vs)) ** 2 for x in vs) / len(vs)) ** 0.5
            ),
            AggregationFunction.PRODUCT: lambda vs: math.prod(vs),
        }

        fn = func_map.get(self.aggregation_func, sum)
        result = fn(values)

        return {
            "result": result,
            "details": f"{self.aggregation_func.name}({values}) = {result}",
            "error": None,
        }

    def _eval_formula(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.formula_template:
            return {"result": True, "details": "empty formula", "error": None}

        # Substitute variables
        formula = self.formula_template
        for var_name, metric_name in self.formula_variables.items():
            value = self._resolve_metric(metric_name, context)
            if value is not None:
                formula = formula.replace(f"{{{var_name}}}", str(value))

        # Safe evaluation of remaining formula
        try:
            # Restrict to basic math for safety
            safe_globals = {
                "__builtins__": {},
                "abs": abs, "round": round, "min": min, "max": max,
                "sum": sum, "pow": pow, "sqrt": math.sqrt, "log": math.log,
            }
            result = eval(formula, safe_globals, {})
            return {
                "result": result,
                "details": f"formula '{self.formula_template}' = {result}",
                "error": None,
            }
        except Exception as e:
            return {
                "result": None,
                "details": str(e),
                "error": f"Formula evaluation error: {e}",
            }

    def _eval_custom(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # Custom functions are resolved by the evaluator
        return {
            "result": True,
            "details": f"custom function '{self.custom_function}' — deferred to evaluator",
            "error": None,
        }

    # ---- Helpers ----

    @staticmethod
    def _resolve_metric(metric: str, context: Dict[str, Any]) -> Any:
        """Resolve a metric name from context dict."""
        if not metric:
            return None
        # Direct key
        if metric in context:
            return context[metric]
        # Nested: a.b.c
        if "." in metric:
            parts = metric.split(".")
            current = context
            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                elif hasattr(current, part):
                    current = getattr(current, part)
                else:
                    return None
            return current
        return None

    @staticmethod
    def _resolve_expression(
        expr: Optional[PolicyExpression], context: Dict[str, Any]
    ) -> Any:
        """Resolve an expression to a scalar value."""
        if expr is None:
            return None
        if expr.expr_type in (ExpressionType.SIMPLE, ExpressionType.COMPARISON):
            return expr._resolve_metric(expr.metric, context)
        result = expr.evaluate(context)
        return result.get("result")

    @staticmethod
    def _compare(a: Any, operator: str, b: Any) -> bool:
        """Compare two values using the given operator string."""
        op_map = {
            "==": _op.eq,
            "!=": _op.ne,
            ">": _op.gt,
            ">=": _op.ge,
            "<": _op.lt,
            "<=": _op.le,
        }
        try:
            fn = op_map.get(operator)
            if fn is None:
                return True
            # Convert to float for numeric comparison
            return fn(float(a), float(b))
        except (TypeError, ValueError):
            # Fall back to string comparison
            fn = op_map.get(operator)
            if fn:
                return fn(str(a), str(b))
            return True

    # ---- Serialization ----

    def to_dict(self) -> Dict[str, Any]:
        return {
            "expression_id": self.expression_id,
            "name": self.name,
            "description": self.description,
            "expr_type": self.expr_type.name,
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
            "threshold_metric": self.threshold_metric,
            "logical_op": self.logical_op.name if self.logical_op else None,
            "left": self.left.to_dict() if self.left else None,
            "right": self.right.to_dict() if self.right else None,
            "arithmetic_op": self.arithmetic_op.name if self.arithmetic_op else None,
            "operands": [op.to_dict() for op in self.operands],
            "aggregation_func": self.aggregation_func.name if self.aggregation_func else None,
            "aggregation_metrics": self.aggregation_metrics,
            "formula_template": self.formula_template,
            "formula_variables": self.formula_variables,
            "custom_function": self.custom_function,
            "custom_args": self.custom_args,
            "severity_on_fail": self.severity_on_fail,
            "enabled": self.enabled,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyExpression":
        expr = cls(
            expression_id=data.get("expression_id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            expr_type=ExpressionType[data.get("expr_type", "SIMPLE")],
            metric=data.get("metric", ""),
            operator=data.get("operator", ""),
            threshold=data.get("threshold"),
            threshold_metric=data.get("threshold_metric", ""),
            severity_on_fail=data.get("severity_on_fail", "WARNING"),
            enabled=data.get("enabled", True),
            tags=data.get("tags", []),
        )
        if data.get("logical_op"):
            expr.logical_op = LogicalOperator[data["logical_op"]]
        if data.get("left"):
            expr.left = cls.from_dict(data["left"])
        if data.get("right"):
            expr.right = cls.from_dict(data["right"])
        if data.get("arithmetic_op"):
            expr.arithmetic_op = ArithmeticOperator[data["arithmetic_op"]]
        for od in data.get("operands", []):
            expr.operands.append(cls.from_dict(od))
        if data.get("aggregation_func"):
            expr.aggregation_func = AggregationFunction[data["aggregation_func"]]
        expr.aggregation_metrics = data.get("aggregation_metrics", [])
        expr.formula_template = data.get("formula_template", "")
        expr.formula_variables = data.get("formula_variables", {})
        expr.custom_function = data.get("custom_function", "")
        expr.custom_args = data.get("custom_args", {})
        return expr


# ---------------------------------------------------------------------------
# Expression builder
# ---------------------------------------------------------------------------

class ExpressionBuilder:
    """Fluent builder for PolicyExpressions."""

    @staticmethod
    def simple(
        metric: str, operator: str, threshold: Any,
        name: str = "", severity: str = "WARNING",
    ) -> PolicyExpression:
        return PolicyExpression(
            expr_type=ExpressionType.SIMPLE,
            metric=metric,
            operator=operator,
            threshold=threshold,
            name=name,
            severity_on_fail=severity,
        )

    @staticmethod
    def logical_and(
        left: PolicyExpression, right: PolicyExpression,
        name: str = "",
    ) -> PolicyExpression:
        return PolicyExpression(
            expr_type=ExpressionType.LOGICAL,
            logical_op=LogicalOperator.AND,
            left=left,
            right=right,
            name=name,
        )

    @staticmethod
    def logical_or(
        left: PolicyExpression, right: PolicyExpression,
        name: str = "",
    ) -> PolicyExpression:
        return PolicyExpression(
            expr_type=ExpressionType.LOGICAL,
            logical_op=LogicalOperator.OR,
            left=left,
            right=right,
            name=name,
        )

    @staticmethod
    def logical_not(
        expr: PolicyExpression, name: str = "",
    ) -> PolicyExpression:
        return PolicyExpression(
            expr_type=ExpressionType.LOGICAL,
            logical_op=LogicalOperator.NOT,
            left=expr,
            name=name,
        )

    @staticmethod
    def aggregation(
        func: AggregationFunction, metrics: List[str],
        name: str = "",
    ) -> PolicyExpression:
        return PolicyExpression(
            expr_type=ExpressionType.AGGREGATION,
            aggregation_func=func,
            aggregation_metrics=metrics,
            name=name,
        )

    @staticmethod
    def formula(
        template: str, variables: Dict[str, str],
        name: str = "",
    ) -> PolicyExpression:
        return PolicyExpression(
            expr_type=ExpressionType.FORMULA,
            formula_template=template,
            formula_variables=variables,
            name=name,
        )
