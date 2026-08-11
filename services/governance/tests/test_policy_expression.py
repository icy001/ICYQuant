"""
Tests for policy_expression.py — PolicyExpression DSL evaluation.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.governance.policy_expression import (
    PolicyExpression,
    ExpressionType,
    ExpressionBuilder,
    LogicalOperator,
    ArithmeticOperator,
    AggregationFunction,
)


class TestPolicyExpressionSimple(unittest.TestCase):
    """Test simple threshold comparison expressions."""

    def test_greater_than_pass(self):
        expr = ExpressionBuilder.simple("price", ">", 100)
        result = expr.evaluate({"price": 150})
        self.assertTrue(result["result"])

    def test_greater_than_fail(self):
        expr = ExpressionBuilder.simple("price", ">", 100)
        result = expr.evaluate({"price": 50})
        self.assertFalse(result["result"])

    def test_less_than_or_equal(self):
        expr = ExpressionBuilder.simple("volume", "<=", 1000)
        self.assertTrue(expr.evaluate({"volume": 1000})["result"])
        self.assertFalse(expr.evaluate({"volume": 1001})["result"])

    def test_equal(self):
        expr = ExpressionBuilder.simple("status", "==", "open")
        self.assertTrue(expr.evaluate({"status": "open"})["result"])

    def test_not_equal(self):
        expr = ExpressionBuilder.simple("status", "!=", "closed")
        self.assertTrue(expr.evaluate({"status": "open"})["result"])

    def test_missing_metric_passes(self):
        expr = ExpressionBuilder.simple("nonexistent", ">", 0)
        result = expr.evaluate({})
        self.assertTrue(result["result"])


class TestPolicyExpressionLogical(unittest.TestCase):
    """Test logical expression combinations."""

    def test_and_both_true(self):
        left = ExpressionBuilder.simple("a", ">", 5)
        right = ExpressionBuilder.simple("b", "<", 10)
        expr = ExpressionBuilder.logical_and(left, right)
        self.assertTrue(expr.evaluate({"a": 7, "b": 8})["result"])

    def test_and_one_false(self):
        left = ExpressionBuilder.simple("a", ">", 5)
        right = ExpressionBuilder.simple("b", "<", 10)
        expr = ExpressionBuilder.logical_and(left, right)
        self.assertFalse(expr.evaluate({"a": 7, "b": 12})["result"])

    def test_or(self):
        left = ExpressionBuilder.simple("a", ">", 100)
        right = ExpressionBuilder.simple("b", "<", 10)
        expr = ExpressionBuilder.logical_or(left, right)
        self.assertTrue(expr.evaluate({"a": 50, "b": 5})["result"])
        self.assertFalse(expr.evaluate({"a": 50, "b": 50})["result"])

    def test_not(self):
        inner = ExpressionBuilder.simple("flag", "==", True)
        expr = ExpressionBuilder.logical_not(inner)
        self.assertFalse(expr.evaluate({"flag": True})["result"])
        self.assertTrue(expr.evaluate({"flag": False})["result"])

    def test_complex_nesting(self):
        # (concentration > 0.3 OR leverage > 2.5) AND liquidity < 50
        expr = PolicyExpression(
            expr_type=ExpressionType.LOGICAL,
            logical_op=LogicalOperator.AND,
            left=PolicyExpression(
                expr_type=ExpressionType.LOGICAL,
                logical_op=LogicalOperator.OR,
                left=ExpressionBuilder.simple("concentration", ">", 0.3),
                right=ExpressionBuilder.simple("leverage", ">", 2.5),
            ),
            right=ExpressionBuilder.simple("liquidity", "<", 50),
        )

        self.assertTrue(
            expr.evaluate({"concentration": 0.5, "leverage": 1.0, "liquidity": 30})["result"]
        )
        self.assertFalse(
            expr.evaluate({"concentration": 0.1, "leverage": 1.0, "liquidity": 60})["result"]
        )


class TestPolicyExpressionAggregation(unittest.TestCase):
    """Test aggregation expressions."""

    def test_sum(self):
        expr = ExpressionBuilder.aggregation(
            AggregationFunction.SUM, ["a", "b", "c"]
        )
        result = expr.evaluate({"a": 10, "b": 20, "c": 30})
        self.assertEqual(result["result"], 60)

    def test_avg(self):
        expr = ExpressionBuilder.aggregation(
            AggregationFunction.AVG, ["a", "b", "c"]
        )
        result = expr.evaluate({"a": 10, "b": 20, "c": 30})
        self.assertEqual(result["result"], 20)

    def test_min_max(self):
        expr_min = ExpressionBuilder.aggregation(
            AggregationFunction.MIN, ["a", "b", "c"]
        )
        expr_max = ExpressionBuilder.aggregation(
            AggregationFunction.MAX, ["a", "b", "c"]
        )
        ctx = {"a": 10, "b": 5, "c": 30}
        self.assertEqual(expr_min.evaluate(ctx)["result"], 5)
        self.assertEqual(expr_max.evaluate(ctx)["result"], 30)

    def test_count(self):
        expr = ExpressionBuilder.aggregation(
            AggregationFunction.COUNT, ["a", "b", "c"]
        )
        self.assertEqual(expr.evaluate({"a": 1, "b": 2, "c": 3})["result"], 3)

    def test_empty_metrics(self):
        expr = ExpressionBuilder.aggregation(AggregationFunction.SUM, [])
        self.assertEqual(expr.evaluate({})["result"], 0.0)


class TestPolicyExpressionSerialization(unittest.TestCase):
    """Test expression serialization round-trip."""

    def test_simple_round_trip(self):
        expr = ExpressionBuilder.simple("price", ">=", 100, name="Price Check")
        data = expr.to_dict()
        restored = PolicyExpression.from_dict(data)
        self.assertEqual(restored.metric, "price")
        self.assertEqual(restored.operator, ">=")
        self.assertEqual(restored.threshold, 100)

    def test_logical_round_trip(self):
        left = ExpressionBuilder.simple("a", ">", 0)
        right = ExpressionBuilder.simple("b", "<", 100)
        expr = ExpressionBuilder.logical_and(left, right, "Range Check")
        data = expr.to_dict()
        restored = PolicyExpression.from_dict(data)
        self.assertEqual(restored.expr_type, ExpressionType.LOGICAL)
        self.assertIsNotNone(restored.left)
        self.assertIsNotNone(restored.right)


class TestNestedMetricResolution(unittest.TestCase):
    """Test nested metric resolution via dot notation."""

    def test_nested_metric(self):
        expr = ExpressionBuilder.simple("portfolio.leverage", ">", 2.0)
        result = expr.evaluate({"portfolio": {"leverage": 3.0}})
        self.assertTrue(result["result"])


if __name__ == "__main__":
    unittest.main()
