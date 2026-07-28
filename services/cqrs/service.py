from .command_handler import CommandHandler
from .query_handler import QueryHandler


class CQRSService:
    def __init__(self):
        self.command_handler = CommandHandler()
        self.query_handler = QueryHandler()

    def execute_command(self, command):
        return self.command_handler.handle(command)

    def execute_query(self, query):
        return self.query_handler.handle(query)
