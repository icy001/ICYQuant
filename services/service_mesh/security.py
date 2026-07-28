class SecurityManager:

    def verify(
        self,
        identity
    ):
        return bool(
            identity.certificate
        )
