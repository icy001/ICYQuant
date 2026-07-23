"""
Trace context propagation.
"""


class TraceContext:

    def __init__(self):
        self.trace_id = None

    def set_trace(
        self,
        trace_id,
    ):
        self.trace_id = trace_id

    def get_trace(self):
        return self.trace_id