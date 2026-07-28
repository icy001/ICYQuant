class ObservabilityService:

    def __init__(self, collector):

        self.collector = collector

    def record(self, metric):

        self.collector.collect(metric)
