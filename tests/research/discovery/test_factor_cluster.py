"""Unit tests for the Alpha Cluster Analysis (research.discovery.factor.cluster)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from research.discovery.factor.cluster import (  # noqa: E402
    cluster_by_correlation,
    decorrelate,
    medoid,
    pairwise_correlation,
)


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #
def _series_from_corr(base: list[float], noise: list[float],
                      rho: float) -> list[float]:
    """y = rho * base_scaled + sqrt(1-rho^2) * noise_scaled (both pre-scaled)."""
    return [rho * b + (1 - rho * rho) ** 0.5 * nz
            for b, nz in zip(base, noise)]


def _mk_series(n: int = 200, seed: int = 7) -> tuple[list[float], ...]:
    """Deterministic pseudo-random base + two independent noise streams."""
    import random
    rng = random.Random(seed)
    base = [rng.gauss(0.0, 1.0) for _ in range(n)]
    n1 = [rng.gauss(0.0, 1.0) for _ in range(n)]
    n2 = [rng.gauss(0.0, 1.0) for _ in range(n)]
    return base, n1, n2


# --------------------------------------------------------------------------- #
# pairwise_correlation                                                         #
# --------------------------------------------------------------------------- #
class TestPairwiseCorrelation:

    def test_per_asset_mean(self):
        base, n1, n2 = _mk_series()
        # asset A: y ~ +0.9 correlated with x; asset B: y ~ -0.9 with x
        x = base
        y_a = _series_from_corr(base, n1, 0.9)
        y_b = _series_from_corr(base, n2, -0.9)
        alphas = ["X", "Y"]
        series = {
            "A": {"X": x, "Y": y_a},
            "B": {"X": x, "Y": y_b},
        }
        corr, n_assets, overlap = pairwise_correlation(series, alphas)
        i, j = 0, 1
        assert corr[i][j] is not None
        # mean of ~+0.9 and ~-0.9 -> near zero
        assert abs(corr[i][j]) < 0.2
        assert n_assets[i][j] == 2
        assert overlap[i][j] == 2 * 200

    def test_none_gaps_respected(self):
        base, n1, _ = _mk_series()
        x = list(base)
        y = _series_from_corr(base, n1, 0.95)
        # punch None holes in y at scattered positions
        for k in range(0, 200, 3):
            y[k] = None
        corr, n_assets, _ = pairwise_correlation({"A": {"X": x, "Y": y}},
                                                 ["X", "Y"])
        assert corr[0][1] > 0.85
        assert n_assets[0][1] == 1

    def test_min_overlap_fail_closed(self):
        base, n1, _ = _mk_series(n=200)
        x = list(base)
        y = _series_from_corr(base, n1, 0.95)
        # only 10 valid overlapping bars -> below MIN_OVERLAP_BARS
        y = [v if k < 10 else None for k, v in enumerate(y)]
        corr, n_assets, _ = pairwise_correlation({"A": {"X": x, "Y": y}},
                                                 ["X", "Y"])
        assert corr[0][1] is None
        assert n_assets[0][1] == 0


# --------------------------------------------------------------------------- #
# cluster_by_correlation                                                       #
# --------------------------------------------------------------------------- #
class TestClusterByCorrelation:

    def test_merges_highly_correlated(self):
        alphas = ["A", "B", "C"]
        corr = [
            [1.0, 0.95, 0.05],
            [0.95, 1.0, 0.10],
            [0.05, 0.10, 1.0],
        ]
        clusters = cluster_by_correlation(alphas, corr, threshold=0.80)
        assert clusters == [["A", "B"], ["C"]]

    def test_negative_corr_same_family(self):
        # |corr| >= threshold -> same family (orientation is learned in-sample)
        alphas = ["A", "B"]
        corr = [[1.0, -0.95], [-0.95, 1.0]]
        clusters = cluster_by_correlation(alphas, corr, threshold=0.80)
        assert clusters == [["A", "B"]]

    def test_undefined_corr_is_unrelated(self):
        # None (never co-measurable) -> distance 1.0 -> separate families
        alphas = ["A", "B", "C"]
        corr = [
            [1.0, None, 0.9],
            [None, 1.0, None],
            [0.9, None, 1.0],
        ]
        clusters = cluster_by_correlation(alphas, corr, threshold=0.80)
        assert ["A", "C"] in clusters
        assert ["B"] in clusters

    def test_singleton_and_empty(self):
        assert cluster_by_correlation([], [[1.0]]) == []
        assert cluster_by_correlation(["A"], [[1.0]]) == [["A"]]


# --------------------------------------------------------------------------- #
# medoid                                                                       #
# --------------------------------------------------------------------------- #
class TestMedoid:

    def test_medoid_is_most_connected(self):
        # B is the hub: A~B 0.9, B~C 0.9, A~C 0.1
        alphas = ["A", "B", "C"]
        corr = [
            [1.0, 0.9, 0.1],
            [0.9, 1.0, 0.9],
            [0.1, 0.9, 1.0],
        ]
        index = {a: i for i, a in enumerate(alphas)}
        rep, intra = medoid(alphas, index, corr)
        assert rep == "B"
        assert intra == pytest.approx((0.9 + 0.9) / 2)

    def test_undefined_counts_as_zero(self):
        alphas = ["A", "B", "C"]
        corr = [
            [1.0, None, 0.8],
            [None, 1.0, 0.9],
            [0.8, 0.9, 1.0],
        ]
        index = {a: i for i, a in enumerate(alphas)}
        rep, _ = medoid(alphas, index, corr)
        # A: (0+0.8)/2=0.4, B: (0+0.9)/2=0.45, C: (0.8+0.9)/2=0.85 -> C wins
        assert rep == "C"


# --------------------------------------------------------------------------- #
# decorrelate (De-correlation Gate)                                            #
# --------------------------------------------------------------------------- #
class TestDecorrelate:

    @staticmethod
    def _factors():
        base, n1, n2 = _mk_series()
        return {
            "A": {
                # X and Y are near-duplicates (rho=0.95); Z independent
                "X": base,
                "Y": _series_from_corr(base, n1, 0.95),
                "Z": n2,
            },
        }

    def test_one_representative_per_family(self):
        alphas = ["X", "Y", "Z"]
        out = decorrelate(alphas, self._factors(),
                          scores={"X": 0.10, "Y": 0.50, "Z": 0.30},
                          threshold=0.65)
        # X and Y merge into one family; Y has the higher score -> kept
        assert out["n_families"] == 2
        assert sorted(out["representatives"]) == ["Y", "Z"]
        fam_xy = next(f for f in out["families"] if "X" in f["members"])
        assert fam_xy["representative"] == "Y"
        assert fam_xy["dropped"] == ["X"]
        assert fam_xy["representative_score"] == 0.50

    def test_low_score_member_dropped(self):
        out = decorrelate(["X", "Y", "Z"], self._factors(),
                          scores={"X": 0.90, "Y": 0.10, "Z": 0.30},
                          threshold=0.65)
        fam_xy = next(f for f in out["families"] if "Y" in f["members"])
        # score wins over medoid-hood: X has the higher score
        assert fam_xy["representative"] == "X"
        assert fam_xy["dropped"] == ["Y"]

    def test_trivial_zero_and_single(self):
        assert decorrelate([], {}, {})["n_families"] == 0
        out = decorrelate(["Only"], {"A": {"Only": [1.0, 2.0]}},
                          scores={"Only": 0.42})
        assert out["representatives"] == ["Only"]
        assert out["families"][0]["representative_score"] == 0.42

    def test_negative_corr_same_family(self):
        # a mirrored twin is the same bet in the opposite direction
        base, n1, n2 = _mk_series()
        factors = {"A": {"X": base,
                         "M": [-b for b in base],
                         "Z": n1}}
        out = decorrelate(["X", "M", "Z"], factors,
                          scores={"X": 0.1, "M": 0.9, "Z": 0.2},
                          threshold=0.65)
        assert out["n_families"] == 2
        assert "M" in out["representatives"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
