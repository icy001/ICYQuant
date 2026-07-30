"""Tests for Drift Detector."""

import pytest
from services.mlops.drift_detector import (
    DriftDetector, DriftConfig, DriftSeverity, DriftMethod,
    DataDriftResult, ModelDriftResult, DriftReport,
)


class TestDriftDetector:
    """Unit tests for DriftDetector."""

    @pytest.fixture
    def config(self):
        return DriftConfig(
            data_drift_threshold_psi=0.2,
            prediction_error_increase_pct=0.3,
        )

    @pytest.fixture
    def detector(self, config):
        return DriftDetector(config)

    # ------------------------------------------------------------------
    # Data Drift
    # ------------------------------------------------------------------

    def test_no_drift_on_similar_data(self, detector):
        ref = {"feature_a": [1.0, 2.0, 3.0, 4.0, 5.0] * 20}
        cur = {"feature_a": [1.0, 2.1, 3.0, 4.0, 5.1] * 20}
        detector.set_reference("TestModel", ref)
        results = detector.check_data_drift("TestModel", cur)
        assert len(results) > 0
        assert results[0].drift_detected is False
        assert results[0].severity == DriftSeverity.NONE

    def test_drift_on_shifted_data(self, detector):
        ref = {"feature_a": [1.0, 2.0, 3.0, 4.0, 5.0] * 100}
        cur = {"feature_a": [10.0, 20.0, 30.0, 40.0, 50.0] * 100}  # Big shift
        detector.set_reference("TestModel", ref)
        results = detector.check_data_drift("TestModel", cur)
        assert len(results) > 0
        assert results[0].drift_detected is True
        assert results[0].severity in (DriftSeverity.HIGH, DriftSeverity.CRITICAL)

    def test_no_reference_returns_empty(self, detector):
        results = detector.check_data_drift("NoRef", {"f1": [1.0, 2.0]})
        assert results == []

    def test_multiple_features(self, detector):
        ref = {
            "f1": [1.0, 2.0, 3.0] * 50,
            "f2": [10.0, 20.0, 30.0] * 50,
        }
        cur = {
            "f1": [1.0, 2.0, 3.0] * 50,
            "f2": [50.0, 60.0, 70.0] * 50,  # Shifted
        }
        detector.set_reference("TestModel", ref)
        results = detector.check_data_drift("TestModel", cur)
        assert len(results) == 2

        # f1 should be fine, f2 should have drift
        f1_result = [r for r in results if r.feature_name == "f1"][0]
        f2_result = [r for r in results if r.feature_name == "f2"][0]
        assert not f1_result.drift_detected
        assert f2_result.drift_detected

    # ------------------------------------------------------------------
    # Model Drift
    # ------------------------------------------------------------------

    def test_model_drift_no_reference(self, detector):
        result = detector.check_model_drift("NoRef", [0.5, 0.6, 0.5])
        assert result is None

    def test_model_drift_similar_predictions(self, detector):
        detector.set_reference(
            "TestModel",
            {"f1": [1.0] * 10},
            predictions=[0.5, 0.6, 0.5, 0.6, 0.5] * 2,
            actuals=[0.5, 0.6, 0.5, 0.6, 0.5] * 2,
        )
        result = detector.check_model_drift(
            "TestModel",
            [0.5, 0.6, 0.5, 0.6, 0.5] * 2,
            [0.5, 0.6, 0.5, 0.6, 0.5] * 2,
        )
        assert result is not None
        assert result.drift_detected is False

    def test_model_drift_different_predictions(self, detector):
        detector.set_reference(
            "TestModel",
            {"f1": [1.0] * 100},
            predictions=[0.1] * 100,
            actuals=[0.1] * 100,
        )
        result = detector.check_model_drift(
            "TestModel",
            [0.9] * 100,  # Very different predictions
            [0.1] * 100,  # Same actuals → accuracy drops
        )
        assert result is not None
        # Should detect drift due to prediction distribution change
        assert result.prediction_psi > 0.1

    # ------------------------------------------------------------------
    # Full Drift Report
    # ------------------------------------------------------------------

    def test_check_drift_full_report(self, detector):
        ref_features = {"f1": [1.0, 2.0, 3.0] * 100}
        detector.set_reference(
            "TestModel",
            ref_features,
            predictions=[0.5] * 100,
            actuals=[0.5] * 100,
        )
        cur_features = {"f1": [1.0, 2.0, 3.0] * 100}

        report = detector.check_drift(
            "TestModel",
            cur_features,
            current_predictions=[0.5] * 100,
            current_actuals=[0.5] * 100,
        )
        assert isinstance(report, DriftReport)
        assert report.model_name == "TestModel"
        assert not report.requires_rollback

    def test_check_drift_no_reference(self, detector):
        report = detector.check_drift(
            "NoModel",
            {"f1": [1.0] * 10},
        )
        assert isinstance(report, DriftReport)
        assert not report.any_data_drift

    # ------------------------------------------------------------------
    # History & Queries
    # ------------------------------------------------------------------

    def test_get_history(self, detector):
        ref = {"f1": [1.0, 2.0, 3.0] * 50}
        detector.set_reference("ModelA", ref)
        detector.check_drift("ModelA", {"f1": [1.0, 2.0, 3.0] * 50})
        detector.check_drift("ModelA", {"f1": [1.0, 2.0, 3.0] * 50})

        history = detector.get_history("ModelA")
        assert len(history) >= 2

    def test_get_latest_report(self, detector):
        ref = {"f1": [1.0, 2.0, 3.0] * 50}
        detector.set_reference("ModelA", ref)
        detector.check_drift("ModelA", {"f1": [1.0, 2.0, 3.0] * 50})

        latest = detector.get_latest_report("ModelA")
        assert latest is not None
        assert latest.model_name == "ModelA"

    # ------------------------------------------------------------------
    # Clear Reference
    # ------------------------------------------------------------------

    def test_clear_reference(self, detector):
        detector.set_reference("ModelA", {"f1": [1.0, 2.0]})
        detector.clear_reference("ModelA")
        results = detector.check_data_drift("ModelA", {"f1": [1.0, 2.0]})
        assert results == []

    # ------------------------------------------------------------------
    # PSI Calculation
    # ------------------------------------------------------------------

    def test_psi_identical_distributions(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0] * 100
        psi = DriftDetector._compute_psi(data, data)
        assert psi < 0.01

    def test_psi_empty_data(self):
        psi = DriftDetector._compute_psi([], [1.0, 2.0])
        assert psi == 0.0

    # ------------------------------------------------------------------
    # KS Test
    # ------------------------------------------------------------------

    def test_ks_test_identical(self):
        d, p = DriftDetector._ks_test(
            [1.0, 2.0, 3.0] * 50,
            [1.0, 2.0, 3.0] * 50,
        )
        assert d < 0.1
        assert p > 0.5

    def test_ks_test_different(self):
        d, p = DriftDetector._ks_test(
            [1.0, 2.0, 3.0] * 50,
            [10.0, 20.0, 30.0] * 50,
        )
        assert d > 0.5
        assert p < 0.05

    # ------------------------------------------------------------------
    # Drift Callbacks
    # ------------------------------------------------------------------

    def test_drift_callback(self, detector):
        ref = {"f1": [1.0, 2.0] * 50}
        cur = {"f1": [100.0, 200.0] * 50}  # Large shift
        detector.set_reference("TestModel", ref)

        drift_events = []

        def on_drift(report):
            drift_events.append(report)

        detector.on_drift(on_drift)
        detector.check_drift("TestModel", cur)

        assert len(drift_events) >= 1

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def test_reset(self, detector):
        detector.set_reference("ModelA", {"f1": [1.0] * 10})
        detector.check_drift("ModelA", {"f1": [1.0] * 10})
        detector.reset()
        assert detector.get_history() == []
