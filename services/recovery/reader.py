class EventReader:
    def __init__(self, repository):
        self.repository = repository

    def read(self, request):
        return self.repository.query(
            request.from_timestamp,
            request.to_timestamp
        )