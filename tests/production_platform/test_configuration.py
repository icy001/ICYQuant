from production_platform.configuration import *


def test_configuration():

    registry = ConfigRegistry()


    manager = ConfigurationManager(

        registry,

        ConfigValidator()

    )


    config = Configuration(

        "risk.limit",

        0.05,

        EnvironmentProfile.PRODUCTION

    )


    assert manager.update(config)


    assert registry.get(

        "risk.limit"

    ).value == 0.05