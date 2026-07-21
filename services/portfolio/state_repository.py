"""
Distributed state repository.
"""


class StateRepository:

    def __init__(self):

        self.states = {}

    def save(
        self,
        state,
    ):

        self.states[
            state.portfolio_id
        ] = state

    def load(
        self,
        portfolio_id,
    ):

        return self.states.get(
            portfolio_id
        )