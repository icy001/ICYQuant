class RegistrationManager:
    def __init__(self, repository):
        self.repository = repository

    def register(self, instance):
        self.repository.save(instance)
        return instance
