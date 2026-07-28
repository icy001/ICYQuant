class SecretManager:
    def __init__(self, repository, encryption):
        self.repository = repository
        self.encryption = encryption

    def store(self, secret):
        secret.value = self.encryption.encrypt(secret.value)
        self.repository.save(secret)
        return secret

    def retrieve(self, secret_id):
        secret = self.repository.get(secret_id)

        if secret:
            secret.value = self.encryption.decrypt(secret.value)

        return secret