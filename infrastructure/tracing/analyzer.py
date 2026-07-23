"""
Trace performance analyzer.
"""


class TraceAnalyzer:

    def analyze(
        self,
        spans,
    ):
        return {
            "count":
                len(spans),
            "status":
                "analyzed"
        }