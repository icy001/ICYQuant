"""测试 Leaderboard & Promotion Manager。

覆盖: 排名与作用域、冠军查询、模型对比、leaderboard 统计、
阶段晋升、评审标准、冠军限制。
"""

import pytest

from services.automl.leaderboard import (
    Leaderboard,
    LeaderboardConfig,
    LeaderboardEntry,
    LeaderboardScope,
    RankMetric,
)
from services.automl.promotion import (
    PromotionConfig,
    PromotionCriteria,
    PromotionManager,
    PromotionResult,
    PromotionStage,
)


# =================================================================
# Leaderboard
# =================================================================


class TestLeaderboardEntry:
    def test_create(self):
        entry = LeaderboardEntry(
            model_name="model_a",
            score=1.5,
            metrics={"sharpe": 1.5, "max_drawdown": 0.15},
            trial_id="trial_001",
            tags=["lightgbm"],
        )
        assert entry.model_name == "model_a"
        assert entry.score == 1.5
        assert entry.metrics["sharpe"] == 1.5
        assert entry.scope == LeaderboardScope.GLOBAL
        assert "lightgbm" in entry.tags

    def test_defaults(self):
        entry = LeaderboardEntry()
        assert entry.rank == 0
        assert entry.model_name == ""


class TestLeaderboardAdd:
    def test_add_single_result(self):
        lb = Leaderboard()
        entry = lb.add_result("model_a", 1.5)
        assert entry.model_name == "model_a"
        assert entry.score == 1.5

    def test_add_entry(self):
        lb = Leaderboard()
        entry = LeaderboardEntry(model_name="model_a", score=2.0)
        lb.add_entry(entry)
        assert entry.rank > 0

    def test_add_multiple_results(self):
        lb = Leaderboard()
        lb.add_result("a", 1.0)
        lb.add_result("b", 2.0)
        lb.add_result("c", 1.5)
        assert lb.entry_count() == 3


class TestLeaderboardRanking:
    @pytest.fixture
    def leaderboard(self):
        lb = Leaderboard(LeaderboardConfig(metric=RankMetric.SHARPE, maximize=True, top_n=50))
        lb.add_result("a", 1.0, {"sharpe": 1.0})
        lb.add_result("b", 3.0, {"sharpe": 3.0})
        lb.add_result("c", 2.0, {"sharpe": 2.0})
        return lb

    def test_ranked_by_metric(self, leaderboard):
        top = leaderboard.top(3)
        assert top[0].model_name == "b"  # highest sharpe
        assert top[1].model_name == "c"
        assert top[2].model_name == "a"
        assert top[0].rank == 1
        assert top[1].rank == 2
        assert top[2].rank == 3

    def test_champion(self, leaderboard):
        champ = leaderboard.champion()
        assert champ is not None
        assert champ.model_name == "b"

    def test_get_rank(self, leaderboard):
        assert leaderboard.get_rank("b") == 1
        assert leaderboard.get_rank("a") == 3
        assert leaderboard.get_rank("nonexistent") is None

    def test_list_models(self, leaderboard):
        models = leaderboard.list_models()
        assert models == ["b", "c", "a"]

    def test_minimize_ranking(self):
        lb = Leaderboard(LeaderboardConfig(metric=RankMetric.SHARPE, maximize=False))
        lb.add_result("a", 1.0, {"sharpe": 1.0})
        lb.add_result("b", 3.0, {"sharpe": 3.0})
        lb.add_result("c", 2.0, {"sharpe": 2.0})
        top = lb.top(3)
        assert top[0].model_name == "a"  # lowest = best


class TestLeaderboardScopes:
    def test_multiple_scopes(self):
        lb = Leaderboard()
        lb.add_result("a", 1.0, scope=LeaderboardScope.MARKET)
        lb.add_result("b", 2.0, scope=LeaderboardScope.GLOBAL)
        lb.add_result("c", 3.0, scope=LeaderboardScope.MARKET)

        assert lb.champion(LeaderboardScope.MARKET).model_name == "c"
        assert lb.champion(LeaderboardScope.GLOBAL).model_name == "b"

    def test_top_n_trims(self):
        cfg = LeaderboardConfig(top_n=3)
        lb = Leaderboard(cfg)
        for i in range(10):
            lb.add_result(f"m{i}", float(10 - i))
        assert lb.entry_count(LeaderboardScope.GLOBAL) == 3

    def test_min_trials_before_rank(self):
        """Entries with fewer than min_trials still rank but config stores threshold."""
        cfg = LeaderboardConfig(min_trials_for_rank=10)
        lb = Leaderboard(cfg)
        assert cfg.min_trials_for_rank == 10
        # Adding entries still works
        lb.add_result("a", 1.0)
        assert lb.top()  # Still has entries


class TestLeaderboardComparison:
    def test_compare(self):
        lb = Leaderboard()
        lb.add_result("a", 10.0, {"sharpe": 2.0, "max_drawdown": 0.1})
        lb.add_result("b", 5.0, {"sharpe": 1.0, "max_drawdown": 0.3})

        result = lb.compare("a", "b")
        assert result["model_a"] == "a"
        assert result["model_b"] == "b"
        assert result["winner"] == "a"
        assert result["a_rank"] < result["b_rank"]
        assert "metric_diff" in result

    def test_compare_missing_model(self):
        lb = Leaderboard()
        lb.add_result("a", 1.0)
        result = lb.compare("a", "b")
        assert result["model_a"] == "a"
        assert result["model_b"] == "b"


class TestLeaderboardStats:
    def test_basic_stats(self):
        lb = Leaderboard()
        lb.add_result("a", 1.0)
        lb.add_result("b", 2.0)
        lb.add_result("c", 3.0)
        stats = lb.stats()
        assert stats["entries"] == 3
        assert stats["champion"] == "c"
        assert stats["best_score"] == 3.0
        assert stats["worst_score"] == 1.0
        assert len(stats["top_models"]) == 3

    def test_empty_stats(self):
        lb = Leaderboard()
        stats = lb.stats()
        assert stats["entries"] == 0


class TestLeaderboardClear:
    def test_clear_scope(self):
        lb = Leaderboard()
        lb.add_result("a", 1.0, scope=LeaderboardScope.GLOBAL)
        lb.add_result("b", 2.0, scope=LeaderboardScope.MARKET)
        lb.clear(scope=LeaderboardScope.GLOBAL)
        assert lb.entry_count(LeaderboardScope.GLOBAL) == 0
        assert lb.entry_count(LeaderboardScope.MARKET) == 1

    def test_clear_all(self):
        lb = Leaderboard()
        lb.add_result("a", 1.0)
        lb.add_result("b", 2.0)
        lb.clear()
        assert lb.entry_count() == 0


# =================================================================
# Promotion Manager
# =================================================================


class TestPromotionConfig:
    def test_default_criteria_exist(self):
        config = PromotionConfig()
        assert len(config.criteria) >= 4

    def test_auto_promote_default(self):
        config = PromotionConfig()
        assert config.auto_promote is True

    def test_require_approval_default(self):
        config = PromotionConfig()
        assert config.require_approval is True

    def test_max_champions(self):
        config = PromotionConfig(max_champions=3)
        assert config.max_champions == 3


class TestPromotionRegister:
    def test_register_default_stage(self):
        pm = PromotionManager()
        pm.register("model_a")
        assert pm.get_stage("model_a") == PromotionStage.EXPERIMENT

    def test_register_custom_stage(self):
        pm = PromotionManager()
        pm.register("model_b", PromotionStage.CHAMPION)
        assert pm.get_stage("model_b") == PromotionStage.CHAMPION

    def test_set_stage(self):
        pm = PromotionManager()
        pm.register("model_a")
        pm.set_stage("model_a", PromotionStage.VALIDATED)
        assert pm.get_stage("model_a") == PromotionStage.VALIDATED

    def test_is_promotable(self):
        pm = PromotionManager()
        pm.register("model_a")
        assert pm.is_promotable("model_a") is True
        pm.set_stage("model_a", PromotionStage.PRODUCTION)
        assert pm.is_promotable("model_a") is False


class TestPromotionEvaluate:
    @pytest.fixture
    def pm(self):
        return PromotionManager()

    def test_promote_to_validated(self, pm):
        pm.register("model_a")
        result = pm.evaluate("model_a", {"sharpe": 1.5, "max_drawdown": 0.2})
        assert result.promoted is True
        assert result.to_stage == PromotionStage.VALIDATED

    def test_not_promoted_insufficient_sharpe(self, pm):
        pm.register("model_a")
        result = pm.evaluate("model_a", {"sharpe": 0.5, "max_drawdown": 0.4})
        assert result.promoted is False
        assert "Sharpe" in result.reason

    def test_not_promoted_drawdown_too_high(self, pm):
        pm.register("model_a")
        result = pm.evaluate("model_a", {"sharpe": 2.0, "max_drawdown": 0.5})
        assert result.promoted is False
        assert "MaxDD" in result.reason

    def test_already_production(self, pm):
        pm.register("prod_model", PromotionStage.PRODUCTION)
        result = pm.evaluate("prod_model", {"sharpe": 3.0, "max_drawdown": 0.05})
        assert result.promoted is False
        assert "Already at highest stage" in result.reason

    def test_auto_promote_disabled(self):
        config = PromotionConfig(auto_promote=False)
        pm = PromotionManager(config)
        pm.register("model_a")
        result = pm.evaluate("model_a", {"sharpe": 3.0, "max_drawdown": 0.05})
        assert result.promoted is False
        assert "Auto-promotion disabled" in result.reason

    def test_champion_requires_walk_forward(self, pm):
        pm.register("model_a", PromotionStage.VALIDATED)
        # Good metrics, but no walk-forward
        result = pm.evaluate("model_a", {
            "sharpe": 2.0, "max_drawdown": 0.15, "stability": 0.7, "ic": 0.03,
        }, has_walk_forward=False)
        assert result.promoted is False
        assert "Walk-forward" in result.reason

    def test_champion_with_walk_forward(self, pm):
        pm.register("model_a", PromotionStage.VALIDATED)
        result = pm.evaluate("model_a", {
            "sharpe": 2.0, "max_drawdown": 0.15, "stability": 0.7,
            "ic_mean": 0.03, "ic": 0.03,
        }, has_walk_forward=True)
        assert result.promoted is True
        assert result.to_stage == PromotionStage.CHAMPION


class TestPromotionChampionLimit:
    def test_max_champions(self):
        config = PromotionConfig(max_champions=1)
        pm = PromotionManager(config)
        # First model: experiment -> validated -> champion
        pm.register("m1", PromotionStage.VALIDATED)
        r1 = pm.evaluate("m1", {
            "sharpe": 2.0, "max_drawdown": 0.15, "stability": 0.7,
            "ic_mean": 0.03, "ic": 0.03,
        }, has_walk_forward=True)
        assert r1.promoted is True
        assert pm.get_stage("m1") == PromotionStage.CHAMPION

        # Second model: should be blocked
        pm.register("m2", PromotionStage.VALIDATED)
        r2 = pm.evaluate("m2", {
            "sharpe": 3.0, "max_drawdown": 0.1, "stability": 0.8,
            "ic_mean": 0.04, "ic": 0.04,
        }, has_walk_forward=True)
        assert r2.promoted is False
        assert "Max champions" in r2.reason


class TestPromotionHumanApproval:
    def test_production_requires_approval(self):
        pm = PromotionManager()
        # Promote through stages
        pm.register("model_a")
        # Validated
        r1 = pm.evaluate("model_a", {"sharpe": 1.5, "max_drawdown": 0.2})
        assert r1.promoted
        # Champion
        pm.set_stage("model_a", PromotionStage.VALIDATED)
        r2 = pm.evaluate("model_a", {
            "sharpe": 2.0, "max_drawdown": 0.15, "stability": 0.7,
            "ic_mean": 0.03, "ic": 0.03,
        }, has_walk_forward=True)
        assert r2.promoted
        # Staging
        pm.set_stage("model_a", PromotionStage.CHAMPION)
        r3 = pm.evaluate("model_a", {
            "sharpe": 2.5, "max_drawdown": 0.1, "stability": 0.75,
            "ic_mean": 0.04, "ic": 0.04,
        }, has_walk_forward=True)
        assert r3.promoted
        # Production -> needs approval
        pm.set_stage("model_a", PromotionStage.STAGING)
        r4 = pm.evaluate("model_a", {
            "sharpe": 2.5, "max_drawdown": 0.08, "stability": 0.85,
            "ic_mean": 0.05, "ic": 0.05,
        }, has_walk_forward=True)
        assert r4.promoted is False
        assert "human approval" in r4.reason.lower()


class TestPromotionBatch:
    def test_evaluate_batch(self):
        pm = PromotionManager()
        candidates = {
            "a": {"sharpe": 2.0, "max_drawdown": 0.1},
            "b": {"sharpe": 0.5, "max_drawdown": 0.5},
        }
        for name in candidates:
            pm.register(name)
        results = pm.evaluate_batch(candidates)
        assert len(results) == 2
        # a should promote, b should not
        assert results[0].promoted
        assert not results[1].promoted


class TestPromotionHistory:
    def test_history_tracks_promotions(self):
        pm = PromotionManager()
        pm.register("model_a")
        pm.evaluate("model_a", {"sharpe": 1.5, "max_drawdown": 0.2})
        history = pm.get_history()
        assert len(history) >= 1
        assert history[-1].model_name == "model_a"

    def test_history_filtering(self):
        pm = PromotionManager()
        pm.register("a")
        pm.register("b")
        pm.evaluate("a", {"sharpe": 1.5, "max_drawdown": 0.2})
        pm.evaluate("b", {"sharpe": 1.5, "max_drawdown": 0.2})
        history_a = pm.get_history("a")
        assert all(r.model_name == "a" for r in history_a)

    def test_demote_archives_model(self):
        pm = PromotionManager()
        pm.register("model_a", PromotionStage.CHAMPION)
        result = pm.demote("model_a", "Underperforming")
        assert result.promoted is False
        assert result.to_stage == PromotionStage.ARCHIVED
        assert pm.get_stage("model_a") == PromotionStage.ARCHIVED


class TestPromotionList:
    def test_list_champions(self):
        pm = PromotionManager()
        pm.register("m1", PromotionStage.CHAMPION)
        pm.register("m2", PromotionStage.EXPERIMENT)
        pm.register("m3", PromotionStage.CHAMPION)
        champions = pm.list_champions()
        assert set(champions) == {"m1", "m3"}

    def test_list_production(self):
        pm = PromotionManager()
        pm.register("m1", PromotionStage.PRODUCTION)
        pm.register("m2", PromotionStage.CHAMPION)
        prod = pm.list_production()
        assert prod == ["m1"]

    def test_get_stage_not_found(self):
        pm = PromotionManager()
        assert pm.get_stage("nonexistent") is None


class TestPromotionCriteriaMet:
    def test_meets_all_criteria(self):
        criteria = PromotionCriteria(
            stage=PromotionStage.CHAMPION,
            min_sharpe=1.5,
            max_drawdown=0.2,
            min_stability=0.6,
            min_ic=0.02,
        )
        metrics = {
            "sharpe": 2.0,
            "max_drawdown": 0.1,
            "stability": 0.8,
            "ic": 0.04,
            "ic_mean": 0.04,
            "win_rate": 0.6,
        }
        assert PromotionManager._meets_criteria(metrics, criteria, True)

    def test_fails_sharpe(self):
        criteria = PromotionCriteria(stage=PromotionStage.VALIDATED, min_sharpe=1.0)
        assert not PromotionManager._meets_criteria({"sharpe": 0.5}, criteria, False)

    def test_fails_drawdown(self):
        criteria = PromotionCriteria(stage=PromotionStage.VALIDATED, max_drawdown=0.3)
        assert not PromotionManager._meets_criteria({"max_drawdown": 0.5}, criteria, False)

    def test_fails_walk_forward(self):
        criteria = PromotionCriteria(stage=PromotionStage.CHAMPION, require_walk_forward=True)
        assert not PromotionManager._meets_criteria({"sharpe": 2.0}, criteria, False)

    def test_failure_reason_detailed(self):
        criteria = PromotionCriteria(
            stage=PromotionStage.CHAMPION, min_sharpe=1.5, max_drawdown=0.2,
        )
        reason = PromotionManager._failure_reason(
            {"sharpe": 0.5, "max_drawdown": 0.3}, criteria, False
        )
        assert "Sharpe" in reason
        assert "MaxDD" in reason
