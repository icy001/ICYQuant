"""Tests for Champion / Challenger Framework."""

import time
import pytest
from services.mlops.champion_challenger import (
    ChampionChallenger, CCConfig, CCStatus, PromotionDecision,
)


class TestChampionChallenger:
    """Unit tests for ChampionChallenger."""

    @pytest.fixture
    def config(self):
        return CCConfig(
            min_evaluation_days=1,
            min_predictions=10,
            max_challengers=3,
            min_consecutive_winning_days=1,
            min_metric_count=2,
            auto_promote=False,
            require_approval=False,
        )

    @pytest.fixture
    def cc(self, config):
        return ChampionChallenger(config)

    # ------------------------------------------------------------------
    # Champion Management
    # ------------------------------------------------------------------

    def test_set_champion(self, cc):
        champ = cc.set_champion(
            "Alpha_v38", "1.0.0", metrics={"sharpe": 2.0, "ic": 0.06}
        )
        assert champ.model_name == "Alpha_v38"
        assert champ.metrics_snapshot["sharpe"] == 2.0

    def test_get_champion_none(self, cc):
        assert cc.get_champion() is None

    def test_get_champion(self, cc):
        cc.set_champion("Alpha_v38", "1.0.0")
        champ = cc.get_champion()
        assert champ is not None
        assert champ.model_name == "Alpha_v38"

    def test_update_champion_metrics(self, cc):
        cc.set_champion("Alpha_v38", "1.0.0", metrics={"sharpe": 2.0})
        cc.update_champion_metrics({"sharpe": 1.8, "ic": 0.05})
        champ = cc.get_champion()
        assert champ.metrics_snapshot["sharpe"] == 1.8
        assert champ.metrics_snapshot["ic"] == 0.05

    # ------------------------------------------------------------------
    # Challenger Management
    # ------------------------------------------------------------------

    def test_add_challenger(self, cc):
        challenger = cc.add_challenger(
            "Alpha_v39", "1.0.1", initial_metrics={"sharpe": 2.2, "ic": 0.07}
        )
        assert challenger is not None
        assert challenger.model_name == "Alpha_v39"
        assert challenger.metrics["sharpe"] == 2.2

    def test_max_challengers(self, cc):
        cc.add_challenger("C1", "1.0.0")
        cc.add_challenger("C2", "1.0.0")
        cc.add_challenger("C3", "1.0.0")
        # 4th should fail
        result = cc.add_challenger("C4", "1.0.0")
        assert result is None

    def test_remove_challenger(self, cc):
        cc.add_challenger("Alpha_v39", "1.0.1")
        assert cc.remove_challenger("Alpha_v39") is True
        assert cc.remove_challenger("Nonexistent") is False

    def test_list_challengers(self, cc):
        cc.add_challenger("C1", "1.0.0")
        cc.add_challenger("C2", "1.0.0")
        challengers = cc.list_challengers()
        assert len(challengers) == 2

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def test_evaluate_no_champion(self, cc):
        cc.add_challenger("Alpha_v39", "1.0.1", initial_metrics={"sharpe": 2.2})
        results = cc.evaluate()
        assert results == []

    def test_evaluate_insufficient_data(self, cc):
        cc.set_champion("Alpha_v38", "1.0.0", metrics={"sharpe": 2.0, "ic": 0.06})
        cc.add_challenger(
            "Alpha_v39", "1.0.1",
            initial_metrics={"sharpe": 2.2, "ic": 0.07}
        )
        results = cc.evaluate()
        # Should hold due to insufficient evaluation days/predictions
        assert len(results) > 0
        assert results[0].decision in (
            PromotionDecision.HOLD, PromotionDecision.REJECT
        )

    def test_evaluate_challenger_wins(self, cc):
        cc.set_champion("Alpha_v38", "1.0.0", metrics={"sharpe": 2.0, "ic": 0.06})
        challenger = cc.add_challenger(
            "Alpha_v39", "1.0.1",
            initial_metrics={"sharpe": 2.5, "ic": 0.08}
        )

        # Simulate enough data
        challenger.evaluation_days = 7
        challenger.predictions_count = 1000
        challenger.consecutive_wins = 5
        challenger.daily_wins = 5

        results = cc.evaluate()
        assert len(results) > 0
        # Should recommend promotion
        assert results[0].decision == PromotionDecision.PROMOTE

    def test_record_prediction(self, cc):
        cc.set_champion("Alpha_v38", "1.0.0")
        cc.add_challenger("Alpha_v39", "1.0.1")
        cc.record_prediction("Alpha_v39", 0.01, 0.02)  # challenger wins
        cc.record_prediction("Alpha_v39", 0.01, 0.005)  # champion wins

        challenger = cc.get_challenger("Alpha_v39")
        assert challenger.predictions_count == 2
        assert challenger.daily_wins == 1
        assert challenger.daily_losses == 1

    # ------------------------------------------------------------------
    # Promotion
    # ------------------------------------------------------------------

    def test_promote_challenger(self, cc):
        cc.set_champion("Alpha_v38", "1.0.0", metrics={"sharpe": 2.0})
        cc.add_challenger("Alpha_v39", "1.0.1", initial_metrics={"sharpe": 2.5})

        result = cc.promote_challenger("Alpha_v39")
        assert result is True

        champion = cc.get_champion()
        assert champion.model_name == "Alpha_v39"
        assert champion.metrics_snapshot["sharpe"] == 2.5

        # Old champion should be removed from challengers
        assert cc.get_challenger("Alpha_v39") is None

    def test_promote_nonexistent(self, cc):
        assert cc.promote_challenger("NoSuchModel") is False

    # ------------------------------------------------------------------
    # Promotion Callbacks
    # ------------------------------------------------------------------

    def test_promotion_callback(self, cc):
        events = []

        def on_promote(challenger, old_champion):
            events.append((challenger.model_name, old_champion.model_name if old_champion else None))

        cc.on_promote(on_promote)
        cc.set_champion("Alpha_v38", "1.0.0", metrics={"sharpe": 2.0})
        cc.add_challenger("Alpha_v39", "1.0.1", initial_metrics={"sharpe": 2.5})
        cc.promote_challenger("Alpha_v39")

        assert len(events) == 1
        assert events[0] == ("Alpha_v39", "Alpha_v38")

    # ------------------------------------------------------------------
    # Status & History
    # ------------------------------------------------------------------

    def test_get_status(self, cc):
        cc.set_champion("Alpha_v38", "1.0.0")
        cc.add_challenger("Alpha_v39", "1.0.1")
        status = cc.get_status()
        assert status["champion"]["model_name"] == "Alpha_v38"
        assert status["challenger_count"] == 1

    def test_get_history(self, cc):
        cc.set_champion("Alpha_v38", "1.0.0", metrics={"sharpe": 2.0, "ic": 0.06})
        challenger = cc.add_challenger("Alpha_v39", "1.0.1", initial_metrics={"sharpe": 2.5, "ic": 0.08})
        # Ensure enough data for evaluation to proceed
        challenger.evaluation_days = 7
        challenger.predictions_count = 1000
        challenger.consecutive_wins = 5
        cc.evaluate()
        history = cc.get_history()
        assert len(history) > 0

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def test_reset(self, cc):
        cc.set_champion("Alpha_v38", "1.0.0")
        cc.add_challenger("Alpha_v39", "1.0.1")
        cc.reset()
        assert cc.get_champion() is None
        assert len(cc.list_challengers()) == 0
