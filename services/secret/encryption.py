class EncryptionService:
    def encrypt(self, value):
        return f"ENC({value})"

    def decrypt(self, value):
        return value.replace("ENC(", "").replace(")", "")