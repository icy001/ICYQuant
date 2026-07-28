from services.config_center import *


def test_configuration_service():

    service = ConfigurationService(
        ConfigurationRepository(),
        ConfigurationValidator()
    )

    config = Configuration(
        "MAX_POSITION",
        "100",
        "PROD"
    )

    result = service.save(config)

    assert result.key == "MAX_POSITION"
