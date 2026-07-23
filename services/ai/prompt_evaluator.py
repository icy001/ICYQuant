"""
Prompt evaluation engine.
"""


class PromptEvaluator:

    def evaluate(
        self,
        prompt,
        output,
    ):

        return {
            "prompt": prompt,
            "score": self._score(output),
        }

    def _score(
        self,
        output,
    ):

        if not output:

            return 0

        return min(
            len(output) / 100,
            1.0,
        )