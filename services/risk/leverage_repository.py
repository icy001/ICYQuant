"""
Leverage rule repository.
"""


class LeverageRepository:

    def __init__(self):

        self.rules = {}

    def save(
        self,
        rule,
    ):

        self.rules[
            rule.account_id
        ] = rule

    def load(
        self,
        account_id,
    ):

        return self.rules.get(
            account_id
        )