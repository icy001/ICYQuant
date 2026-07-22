"""
Cache metrics.
"""


class CacheMetrics:

    def __init__(self):

        self.hit = 0

        self.miss = 0

    def record_hit(self):

        self.hit += 1

    def record_miss(self):

        self.miss += 1

    @property
    def hit_rate(self):

        total = self.hit + self.miss

        if total == 0:

            return 0.0

        return self.hit / total