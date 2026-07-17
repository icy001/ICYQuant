"""
Portfolio covariance model.
"""

from __future__ import annotations


class CovarianceMatrix:
    def __init__(
        self,
        matrix,
    ):
        self.matrix = matrix

    def get(
        self,
        asset_a,
        asset_b,
    ):
        return self.matrix.get(
            (asset_a, asset_b)
        )