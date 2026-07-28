class CacheRepository:

    def __init__(self):
        self.cache = {}

    def put(self, entry):
        self.cache[entry.key] = entry

    def get(self, key):
        return self.cache.get(key)
