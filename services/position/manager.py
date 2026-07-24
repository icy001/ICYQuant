class PositionManager:

    def __init__(
        self,
        repository,
    ):
        self.repository = repository

    def open(
        self,
        position,
    ):
        self.repository.save(
            position
        )
        return position

    def get(
        self,
        position_id,
    ):
        return self.repository.find(
            position_id
        )