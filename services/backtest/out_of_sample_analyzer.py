"""
Out-of-sample analyzer.
"""

from .out_of_sample_result import (
    OutOfSampleResult,
)


class OutOfSampleAnalyzer:

    def analyze(
        self,
        parameters,
        performance,
    ):

        return OutOfSampleResult(
            parameters,
            performance,
        )