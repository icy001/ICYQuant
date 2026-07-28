class WorkflowDAG:
    def __init__(self):
        self.nodes = []

    def add(self, task):
        self.nodes.append(task)

    def tasks(self):
        return self.nodes
