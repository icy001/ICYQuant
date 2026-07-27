class RiskRepository:
    def __init__(self):
        self.rules = {}

    def save(self, rule):
        self.rules[rule.rule_id] = rule

    def find(self, rule_id):
        return self.rules.get(rule_id)