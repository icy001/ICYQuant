class TraceAnalyzer:

    def latency(
        self,
        spans
    ):
        return sum(
            span.duration
            for span in spans
        )
