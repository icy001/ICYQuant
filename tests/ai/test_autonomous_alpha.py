from services.ai import AlphaCandidate


def test_alpha_candidate():

    alpha = AlphaCandidate(
        "Momentum",
        "close/ma20",
        "trend",
        {},
    )

    assert alpha.name == "Momentum"