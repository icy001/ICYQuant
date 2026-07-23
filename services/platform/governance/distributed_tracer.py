"""
Distributed tracing.
"""

import uuid


class DistributedTracer:

    def start_span(
        self,
        operation,
    ):

        return {
            "trace_id": str(
                uuid.uuid4()
            ),
            "operation": operation,
        }