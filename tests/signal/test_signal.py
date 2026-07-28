from services.signal import *


def test_signal():

    repo = SignalRepository()

    service = SignalService(repo)

    signal = Signal(

        "SIG001",

        "NVDA",

        "BUY",

        0.9

    )

    service.create(signal)

    result = service.query(
        "SIG001"
    )

    assert result.score == 0.9
