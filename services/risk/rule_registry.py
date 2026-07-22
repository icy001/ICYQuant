"""
Rule registry.
"""


class RuleRegistry:

    def __init__(self):

        self.registry = {}

    def register(
        self,
        rule,
    ):

        self.registry[rule.rule_id] = rule

    def resolve(
        self,
        rule_id,
    ):

        return self.registry.get(rule_id)