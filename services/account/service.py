class AccountService:


    def __init__(

        self,

        manager,

    ):

        self.manager = manager



    def open_account(

        self,

        account,

    ):

        return self.manager.create(

            account

        )



    def query_account(

        self,

        account_id,

    ):

        return self.manager.get(

            account_id

        )