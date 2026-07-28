class AlertEngine:

    def evaluate(self, metric):

        if metric.value > 100:

            return "ALERT"

        return "OK"
