"""
Notebook runtime.
"""


class NotebookRuntime:

    def execute(
        self,
        notebook,
    ):

        return {
            "notebook_id": notebook.notebook_id,
            "status": "SUCCESS",
        }