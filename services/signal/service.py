class SignalService:

    def __init__(self, repository):

        self.repository = repository

    def create(self, signal):

        self.repository.save(signal)

    def query(self, signal_id):

        return self.repository.get(signal_id)
