class IntelligenceService:

    def __init__(self):

        self.modules = []

    def register(self, module):

        self.modules.append(module)

    def execute(self, context):

        results = []

        for module in self.modules:

            results.append(
                module.run(context)
            )

        return results
