class HotReloadManager:

    def reload(self, config):
        return {
            "status": "RELOADED",
            "config": config.key
        }
