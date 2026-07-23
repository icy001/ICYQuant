"""
Prompt version storage.
"""


class PromptVersionStore:

    def __init__(self):

        self._versions = {}

    def save(
        self,
        version,
    ):

        self._versions.setdefault(
            version.prompt_id,
            []
        ).append(
            version
        )

    def latest(
        self,
        prompt_id,
    ):

        versions = self._versions.get(
            prompt_id,
            []
        )

        if not versions:

            return None

        return versions[-1]