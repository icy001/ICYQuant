class CacheMetrics:

    def __init__(self):
        self.hit = 0

        self.miss = 0

    def hit_rate(self):
        total = self.hit + self.miss

        return self.hit / total if total else 0
