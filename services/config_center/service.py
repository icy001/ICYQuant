class ConfigurationService:

    def __init__(
        self,
        repository,
        validator
    ):
        self.repository = repository
        self.validator = validator

    def save(self, config):
        if not self.validator.validate(config):
            raise ValueError("Invalid configuration")

        self.repository.save(config)

        return config
