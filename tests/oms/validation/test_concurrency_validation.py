"""Tests for concurrency validation — optimistic locking."""

import unittest

from services.oms.validation.concurrency_validator import ConcurrencyValidator
from services.oms.validation.quantity_validator import QuantityValidator
from services.oms.results.command_errors import (
    ConcurrencyConflictError,
    QuantityExceededError,
    CommandValidationError,
)


class TestConcurrencyValidation(unittest.TestCase):

    def test_version_match_passes(self):
        ConcurrencyValidator.validate("CMD-1", "ORD-1", 5, 5)

    def test_version_mismatch_fails(self):
        with self.assertRaises(ConcurrencyConflictError):
            ConcurrencyValidator.validate("CMD-1", "ORD-1", 5, 6)

    def test_none_expected_skips_check(self):
        ConcurrencyValidator.validate("CMD-1", "ORD-1", 0, 100)

    def test_needs_check(self):
        self.assertTrue(ConcurrencyValidator.needs_check(5))
        self.assertFalse(ConcurrencyValidator.needs_check(0))


class TestQuantityValidation(unittest.TestCase):

    def test_valid_fill(self):
        QuantityValidator.validate_fill("ORD-1", "CMD-1", 300, 700, 1000)

    def test_fill_exceeds_remaining(self):
        with self.assertRaises(QuantityExceededError):
            QuantityValidator.validate_fill("ORD-1", "CMD-1", 800, 700, 1000)

    def test_zero_fill_rejected(self):
        with self.assertRaises(CommandValidationError):
            QuantityValidator.validate_fill("ORD-1", "CMD-1", 0, 700, 1000)

    def test_parent_quantity_exceeded(self):
        with self.assertRaises(QuantityExceededError):
            QuantityValidator.validate_parent("ORD-1", "CMD-1", 12000, 10000)

    def test_invariant_valid(self):
        self.assertTrue(QuantityValidator.validate_invariant(
            "ORD-1", 600, 400, 0, 1000,
        ))

    def test_invariant_invalid(self):
        self.assertFalse(QuantityValidator.validate_invariant(
            "ORD-1", 600, 500, 0, 1000,
        ))


if __name__ == '__main__':
    unittest.main()
