class SecretManager:

    def __init__(

        self,

        vault,

        accessor,

    ):

        self.vault = vault

        self.accessor = accessor

    def store(

        self,

        secret,

    ):

        self.vault.save(secret)

    def retrieve(

        self,

        role,

        name,

    ):

        return self.accessor.read(

            role,

            name,

        )