class AccountRepository:


    def __init__(self):

        self.accounts = {}



    def save(

        self,

        account,

    ):

        self.accounts[account.account_id] = account



    def find(

        self,

        account_id,

    ):

        return self.accounts.get(account_id)