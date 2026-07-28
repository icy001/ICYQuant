class DistributedCacheManager:

    def __init__(self):
        self.cluster = {}

    def put(self, key, value):
        self.cluster[key] = value

    def get(self, key):
        return self.cluster.get(key)
