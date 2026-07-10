from services.reconciliation import (
    ConflictResolutionEngine,
    ResolutionAction,
)


def test_same_value_no_conflict():
    engine = ConflictResolutionEngine()

    result = engine.resolve(
        {
            "BROKER":
                100,
            "LEDGER":
                100
        }
    )

    assert (
        result
        ==
        ResolutionAction.IGNORE
    )


def test_conflict_requires_review():
    engine = ConflictResolutionEngine()

    result = engine.resolve(
        {
            "BROKER":
                100,
            "LEDGER":
                80,
            "MANUAL":
                120
        }
    )

    assert (
        result
        ==
        ResolutionAction.REQUIRE_APPROVAL
    )