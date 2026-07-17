"""
Information coefficient analyzer.
"""

from __future__ import annotations


class ICAnalyzer:
    def calculate(
        self,
        factor_values,
        returns,
    ):
        if not factor_values:
            return 0

        factor_avg = sum(factor_values) / len(factor_values)
        return_avg = sum(returns) / len(returns)

        numerator = sum(
            (f - factor_avg) * (r - return_avg)
            for f, r in zip(factor_values, returns)
        )

        return numerator