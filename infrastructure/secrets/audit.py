class SecretAudit:

    def log(

        self,

        action,

        secret_name,

    ):

        return {

            "action": action,

            "secret": secret_name,

        }