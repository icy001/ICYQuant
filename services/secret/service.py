class SecretService:
    def __init__(self, manager):
        self.manager = manager

    def save(self, secret):
        return self.manager.store(secret)

    def get(self, secret_id):
        return self.manager.retrieve(secret_id)