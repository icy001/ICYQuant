"""
Strategy research pipeline.
"""

from __future__ import annotations


class ResearchPipeline:
    def run(
        self,
        experiment,
        backtest,
    ):
        result = backtest.run(experiment)

        return result