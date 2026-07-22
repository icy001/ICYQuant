from services.risk import (
    RiskFactory,
)


def test_create_domain():
    domain = RiskFactory().create(
        "RISK-DOMAIN",
    )

    assert domain.name == "Risk"