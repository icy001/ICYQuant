class SecretVault:

    def __init__(self):

        self._storage = {}

    def save(self, secret):

        self._storage[secret.name] = secret

    def get(self, name):

        return self._storage.get(name)