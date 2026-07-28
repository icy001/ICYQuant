class ConfigurationService:
    def __init__(self, repository, loader):
        self.repository = repository
        self.loader = loader

    def get(self, key, environment):
        config = self.repository.get(key, environment)

        if not config:
            return None

        return self.loader.load(config)