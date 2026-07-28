class TraceRepository:

    def __init__(self):
        self.traces = []

    def save(
        self,
        trace
    ):
        self.traces.append(trace)

    def all(
        self
    ):
        return self.traces
