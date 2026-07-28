class ConfigurationPublisher:

    def publish(self, config):
        return {
            "event": "CONFIG_UPDATED",
            "key": config.key
        }
