class AccountManager:


    def __init__(

        self,

        repository,

    ):

        self.repository = repository



    def create(

        self,

        account,

    ):

        self.repository.save(account)

        return account



    def get(

        self,

        account_id,

    ):

        return self.repository.find(

            account_id

        )