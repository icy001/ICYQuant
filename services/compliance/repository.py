class ComplianceRepository:
    def __init__(self):
        self.rules = {}
        self.records = {}

    def save_rule(self, rule):
        self.rules[rule.rule_id] = rule

    def save_record(self, record):
        self.records[record.record_id] = record