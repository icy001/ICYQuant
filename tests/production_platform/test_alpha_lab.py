from services.platform.quant import (
    Factor,
    FactorResearchEngine,
)


def test_factor():

    engine = FactorResearchEngine()

    engine.register(
        Factor(
            "momentum",
            "price",
            "close/ma20",
        )
    )

    assert len(
        engine.research()
    ) == 1