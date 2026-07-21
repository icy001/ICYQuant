"""
State recovery.
"""


class StateRecovery:

    def recover(
        self,
        repository,
        portfolio_id,
    ):

        return repository.load(
            portfolio_id
        )