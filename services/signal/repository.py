class SignalRepository:

    def __init__(self):

        self.data = {}

    def save(self, signal):

        self.data[
            signal.signal_id
        ] = signal

    def get(self, signal_id):

        return self.data.get(signal_id)
