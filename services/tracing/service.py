class TracingService:

    def __init__(
        self,
        repository,
        collector
    ):
        self.repository = repository
        self.collector = collector

    def create_trace(
        self,
        trace
    ):
        self.repository.save(
            trace
        )

        return trace

    def add_span(
        self,
        span
    ):
        self.collector.collect(
            span
        )

        return span
