class PositionService:

    def __init__(
        self,
        manager,
    ):
        self.manager = manager

    def create_position(
        self,
        position,
    ):
        return self.manager.open(
            position
        )

    def query_position(
        self,
        position_id,
    ):
        return self.manager.get(
            position_id
        )