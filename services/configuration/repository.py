class ConfigurationRepository:
    def __init__(self):
        self.configs = {}

    def save(self, config):
        self.configs[(config.key, config.environment)] = config

    def get(self, key, environment):
        return self.configs.get((key, environment))