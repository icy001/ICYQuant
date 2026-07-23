"""
Production configuration pipeline.
"""


class ConfigurationPipeline:

    def __init__(
        self,
        loader,
        validator,
    ):
        self.loader = loader
        self.validator = validator

    def execute(
        self,
        source,
    ):
        config = self.loader.load(
            source
        )

        return self.validator.validate(
            config
        )