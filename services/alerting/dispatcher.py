class AlertDispatcher:

    def dispatch(self, alert):
        alert.status = "DISPATCHED"

        return alert
