class TraceContext:

    def __init__(self):
        self.current_trace = None

    def set(
        self,
        trace_id
    ):
        self.current_trace = trace_id

    def get(
        self
    ):
        return self.current_trace
