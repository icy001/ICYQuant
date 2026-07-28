class LimiterRepository:

    def __init__(self):
        self.rules = {}

    def save(self, rule):
        self.rules[rule.resource] = rule

    def get(self, resource):
        return self.rules.get(resource)
