class SecretRepository:
    def __init__(self):
        self.secrets = {}

    def save(self, secret):
        self.secrets[secret.secret_id] = secret

    def get(self, secret_id):
        return self.secrets.get(secret_id)