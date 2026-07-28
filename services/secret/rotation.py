class SecretRotationManager:
    def rotate(self, secret, new_value):
        secret.value = new_value
        return secret