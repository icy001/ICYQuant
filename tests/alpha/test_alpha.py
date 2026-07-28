from services.alpha import *


def test_alpha():

    repo = AlphaRepository()

    service = AlphaService(repo)

    alpha = Alpha(

        "A001",

        "Momentum",

        0.85

    )

    service.register(alpha)

    result = service.query(
        "A001"
    )

    assert result.score == 0.85
