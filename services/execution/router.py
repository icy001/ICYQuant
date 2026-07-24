class ExecutionRouter:

    def __init__(self):
        self.adapters = {}

    def register(
        self,
        name,
        adapter,
    ):
        self.adapters[name] = adapter

    def route(
        self,
        name,
        request,
    ):
        adapter = self.adapters.get(name)

        if not adapter:
            raise Exception(
                "Adapter not found"
            )

        return adapter.execute(request)