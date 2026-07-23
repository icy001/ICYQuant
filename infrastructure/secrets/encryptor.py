import base64


class Encryptor:

    def encrypt(self, value: str):

        return base64.b64encode(
            value.encode()
        ).decode()

    def decrypt(self, value: str):

        return base64.b64decode(
            value.encode()
        ).decode()