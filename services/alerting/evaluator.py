class RuleEvaluator:

    def evaluate(self, value, rule):

        if rule.operator == ">":
            return value > rule.threshold

        if rule.operator == "<":
            return value < rule.threshold

        return False
