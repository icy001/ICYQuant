class CacheMetrics:

    def __init__(self):

        self.hit = 0

        self.miss = 0

    def record_hit(self):

        self.hit += 1

    def record_miss(self):

        self.miss += 1