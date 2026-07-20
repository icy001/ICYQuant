"""
Portfolio compliance engine.
"""


class PortfolioComplianceEngine:
    def __init__(
        self,
        detector,
    ):
        self.detector = detector

    def evaluate(
        self,
        rules,
        values,
    ):
        violations = []

        for rule in rules:
            value = values.get(rule.rule_id, 0)
            result = self.detector.detect(rule, value)

            if result:
                violations.append(result)

        return violations