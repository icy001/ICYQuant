"""
Fund intelligence brain.
"""


class FundIntelligenceBrain:

    def __init__(
        self,
        feedback,
        learner,
        knowledge,
    ):
        self.feedback = feedback
        self.learner = learner
        self.knowledge = knowledge

    def improve(
        self,
        result,
    ):
        feedback = self.feedback.analyze(
            result
        )
        learning = self.learner.learn(
            feedback
        )
        return self.knowledge.reinforce(
            learning
        )