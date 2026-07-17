"""
Feature computation pipeline.
"""

from __future__ import annotations


class FeaturePipeline:
    def __init__(
        self,
        calculators,
    ):
        self.calculators = calculators

    def run(
        self,
        data,
    ):
        results = []

        for calculator in self.calculators:
            results.append(calculator.calculate(data))

        return results