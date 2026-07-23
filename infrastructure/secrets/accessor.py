class SecretAccessor:

    def __init__(

        self,

        vault,

        policy,

    ):

        self.vault = vault

        self.policy = policy

    def read(

        self,

        role,

        name,

    ):

        if not self.policy.allow(role):

            raise PermissionError()

        return self.vault.get(name)