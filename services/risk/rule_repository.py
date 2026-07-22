"""
Risk rule repository.
"""


class RuleRepository:

    def __init__(self):

        self.rules = {}

    def save(
        self,
        rule,
    ):

        self.rules[rule.rule_id] = rule

    def get(
        self,
        rule_id,
    ):

        return self.rules.get(rule_id)

    def list_all(self):

        return list(self.rules.values())