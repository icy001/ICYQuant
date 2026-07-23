from infrastructure.logging import Logger


def test_logger():

    logger = Logger(
        "trading-engine"
    )

    event = logger.info(
        "order received"
    )

    assert event["level"] == "INFO"