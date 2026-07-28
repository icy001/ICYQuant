class CacheService:

    def __init__(
        self,
        repository
    ):
        self.repository = repository

    def put(self, entry):
        self.repository.put(entry)

    def get(self, key):
        return self.repository.get(key)
