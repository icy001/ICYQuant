class WorkflowDAG:


    def __init__(self):

        self.nodes = {}

        self.edges = {}



    def add_task(

        self,

        task,

    ):

        self.nodes[task.name] = task



    def add_dependency(

        self,

        before,

        after,

    ):

        self.edges.setdefault(

            before,

            []

        ).append(after)