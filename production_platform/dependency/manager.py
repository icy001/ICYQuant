class DependencyManager:


    def __init__(

        self,

        container,

    ):

        self.container = container



    def install(

        self,

        module,

    ):

        for dep in module.dependencies:

            self.container.register(

                dep.name,

                dep.implementation

            )