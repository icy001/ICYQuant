class HistogramCollector:

    def collect(
        self,
        values
    ):
        return {
            "count": len(values),
            "avg": sum(values) / len(values)
        }
