class DeploymentManager:

    def __init__(self):

        self.models = {}

    def deploy(self, name, model):

        self.models[name] = model

    def get(self, name):

        return self.models.get(name)
