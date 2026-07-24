class PositionRepository:

    def __init__(self):
        self.positions = {}

    def save(
        self,
        position,
    ):
        self.positions[
            position.position_id
        ] = position

    def find(
        self,
        position_id,
    ):
        return self.positions.get(
            position_id
        )