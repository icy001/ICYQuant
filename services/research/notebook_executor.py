"""
Notebook executor.
"""


class NotebookExecutor:

    def __init__(
        self,
        runtime,
    ):

        self.runtime = runtime

    def run(
        self,
        notebook,
    ):

        return self.runtime.execute(
            notebook
        )