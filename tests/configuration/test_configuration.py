from services.configuration import *


def test_configuration_service():
    repository = ConfigurationRepository()

    config = Configuration(
        "MAX_POSITION",
        "100000",
        Environment.PRODUCTION,
        1
    )

    repository.save(config)

    service = ConfigurationService(
        repository,
        ConfigurationLoader()
    )

    value = service.get("MAX_POSITION", Environment.PRODUCTION)

    assert value == "100000"