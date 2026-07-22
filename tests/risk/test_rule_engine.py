from services.risk import (
    RiskRule,
    RuleEvaluator,
    RulePipeline,
    RuleRepository,
    RiskRuleEngine,
)


def test_rule_engine():
    repository = RuleRepository()

    repository.save(
        RiskRule(
            "RULE-001",
            "Position Limit",
            True,
            {},
        )
    )

    engine = RiskRuleEngine(
        repository,
        RulePipeline(
            RuleEvaluator(),
        ),
    )

    result = engine.execute({})

    assert result == [True]