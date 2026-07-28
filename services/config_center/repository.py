class ConfigurationRepository:

    def __init__(self):
        self.configs = {}

    def save(self, config):
        self.configs[config.key] = config

    def get(self, key):
        return self.configs.get(key)
