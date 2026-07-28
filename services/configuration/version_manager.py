class VersionManager:
    def upgrade(self, config):
        config.version += 1
        return config

    def rollback(self, config):
        if config.version > 0:
            config.version -= 1
        return config