class RolloutManager:

    def rollout(self, rule):
        return {
            "percentage": rule.percentage,
            "group": rule.target_group
        }
